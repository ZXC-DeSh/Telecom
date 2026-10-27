import json
import logging
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path

import numpy as np
from catboost import CatBoostClassifier, EFstrType, Pool

from app.core.config import Settings
from app.domain.entities.call import Call
from app.domain.entities.model_info import ModelInfo, ModelMetrics
from app.domain.entities.prediction import Prediction
from app.domain.entities.prediction_reason import PredictionReason
from app.domain.exceptions import FeatureUnavailable
from app.domain.repositories.calls import CallRepository
from app.domain.value_objects import CallType, FraudScenario, Recommendation, RiskLevel
from app.infrastructure.ml.features import (
    FeatureValue,
    build_features,
    validate_feature_contract,
)

logger = logging.getLogger(__name__)


class CatBoostPredictor:
    def __init__(self, settings: Settings, calls: CallRepository | None = None) -> None:
        self.model: CatBoostClassifier | None = None
        self.model_passport: ModelInfo | None = None
        self._calls = calls
        self._feature_names: tuple[str, ...] = ()
        self._fraud_threshold = 0.5

        try:
            self._load_model(settings.model_path)
            self._load_model_info(settings.model_passport_path)
        except Exception:
            self.model = None
            self.model_passport = None
            logger.exception("CatBoost model initialization failed")

    def _load_model(self, path: str | Path) -> None:
        model_path = Path(path)

        if not model_path.is_file():
            raise FileNotFoundError(f"Файл модели не найден: {model_path}")

        model = CatBoostClassifier()
        model.load_model(str(model_path))

        self.model = model

    def _load_model_info(self, path: str | Path) -> None:
        info_path = Path(path)

        if not info_path.is_file():
            raise FileNotFoundError(f"Файл метаданных модели не найден: {info_path}")

        with info_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        metrics_data = data.get("metrics")
        metrics = ModelMetrics(**metrics_data) if metrics_data is not None else None

        trained_at = data.get("trained_at")
        if trained_at is not None:
            try:
                trained_at = datetime.fromisoformat(trained_at)
            except ValueError:
                trained_at = datetime.strptime(trained_at, "%Y.%m.%d")

        self._feature_names = tuple(data.get("feature_names", ()))
        if len(self._feature_names) != len(set(self._feature_names)):
            raise ValueError("имена признаков модели должны быть уникальными")
        if "call_type" not in self._feature_names:
            raise ValueError("среди признаков модели должен быть call_type")
        self._fraud_threshold = float(data.get("evaluation_threshold", 0.5))
        if not 0 < self._fraud_threshold < 1:
            raise ValueError("evaluation_threshold модели должен быть от 0 до 1")

        self.model_passport = ModelInfo(
            name=data["name"],
            version=data["version"],
            is_loaded=self.model is not None,
            algorithm=data.get("algorithm", "CatBoost"),
            trained_at=trained_at,
            feature_names=tuple(data.get("feature_names", [])),
            metrics=metrics,
        )

    def is_available(self) -> bool:
        return (
            self.model is not None
            and self.model_passport is not None
            and self.model_passport.is_loaded
        )

    def predict(self, call: Call) -> Prediction:
        if not self.is_available() or self.model is None:
            raise FeatureUnavailable("модель CatBoost недоступна")
        if self._calls is None:
            raise FeatureUnavailable("источник истории вызовов не настроен")
        if not self._feature_names:
            raise FeatureUnavailable("имена признаков модели не настроены")

        raw_model_names = self.model.feature_names_
        model_names = tuple(raw_model_names) if raw_model_names is not None else ()
        if model_names and model_names != self._feature_names:
            raise FeatureUnavailable(
                "имена признаков модели не совпадают с её паспортом"
            )
        if self.model.get_cat_feature_indices():
            raise FeatureUnavailable(
                "модель ожидает категориальные признаки, но конвейер признаков "
                "передаёт числовые признаки"
            )

        history = self._calls.history_before(call)
        features = build_features(call, history)
        try:
            values = validate_feature_contract(features, self._feature_names)
        except ValueError as exc:
            raise FeatureUnavailable(
                f"Некорректный контракт признаков модели: {exc}"
            ) from exc
        pool = Pool(
            data=[values],
            feature_names=list(self._feature_names),
        )
        probabilities = self.model.predict_proba(pool)[0]
        raw_classes = self.model.classes_
        if raw_classes is None:
            raise FeatureUnavailable("классы модели недоступны")
        classes = tuple(raw_classes)
        positive_class_index = next(
            (index for index, label in enumerate(classes) if label in (1, True, "1")),
            None,
        )
        if positive_class_index is None:
            raise FeatureUnavailable(
                "модель не предоставляет положительный класс мошенничества"
            )

        risk_score = float(probabilities[positive_class_index])
        risk_level = _risk_level(risk_score)
        is_fraud = risk_score >= self._fraud_threshold
        reasons = self._explain(pool, values)
        return Prediction(
            call_id=call.id,
            risk_score=risk_score,
            risk_level=risk_level,
            is_fraud=is_fraud,
            fraud_scenario=(
                _fraud_scenario(call, history, features) if is_fraud else None
            ),
            recommendation=_recommendation(risk_level),
            reasons=reasons,
        )

    def _explain(
        self, pool: Pool, values: Sequence[FeatureValue]
    ) -> tuple[PredictionReason, ...]:
        if self.model is None:
            return ()
        try:
            shap_values = self.model.get_feature_importance(
                pool, type=EFstrType.ShapValues
            )
            if shap_values is None:
                raise ValueError("CatBoost не вернул значения SHAP")
            contributions = np.asarray(shap_values)[0, :-1]
            if len(contributions) != len(self._feature_names):
                raise ValueError("CatBoost вернул вектор SHAP неожиданного размера")
            ranked = sorted(
                range(len(contributions)),
                key=lambda index: abs(float(contributions[index])),
                reverse=True,
            )[:5]
        except Exception as exc:
            logger.exception("Unable to calculate CatBoost SHAP explanations")
            raise FeatureUnavailable("объяснение риска вызова недоступно") from exc

        reasons: list[PredictionReason] = []
        for index in ranked:
            contribution = float(contributions[index])
            feature = self._feature_names[index]
            value = values[index]
            label = _feature_description(feature, value)
            impact = (
                "increases_risk"
                if contribution > 1e-9
                else "decreases_risk"
                if contribution < -1e-9
                else "no_material_effect"
            )
            reasons.append(
                PredictionReason(
                    feature=feature,
                    value=value,
                    impact=impact,
                    contribution=contribution,
                    description=label,
                )
            )
        return tuple(reasons)

    def get_info(self) -> ModelInfo:
        if self.model_passport is None:
            raise FeatureUnavailable("метаданные модели не настроены")

        return self.model_passport


def _risk_level(score: float) -> RiskLevel:
    if score < 0.25:
        return RiskLevel.LOW
    if score < 0.5:
        return RiskLevel.MEDIUM
    if score < 0.75:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


def _recommendation(level: RiskLevel) -> Recommendation:
    if level == RiskLevel.LOW:
        return Recommendation.MONITOR
    if level in (RiskLevel.MEDIUM, RiskLevel.HIGH):
        return Recommendation.MANUAL_REVIEW
    return Recommendation.ESCALATE


def _fraud_scenario(
    call: Call,
    history: tuple[Call, ...],
    features: Mapping[str, FeatureValue],
) -> FraudScenario:
    a_history = tuple(item for item in history if item.msisdn_a == call.msisdn_a)
    recent = tuple(
        item
        for item in a_history
        if (call.call_time - item.call_time).total_seconds() <= 86400
    )
    scores = {scenario: 0 for scenario in FraudScenario}

    if call.duration_seconds <= 2 or features["is_zero_duration"]:
        scores[FraudScenario.WANGIRI] += 2
    if features["a_b_prior_short_probe_then_long_call"]:
        scores[FraudScenario.VISHING_SPOOFING] += 4
    if (
        call.duration_seconds >= 420
        and _numeric_feature(features, "a_short_calls_24h") >= 4
    ):
        scores[FraudScenario.VISHING_SPOOFING] += 2
    if (
        _numeric_feature(features, "a_unique_contacts_out_1h") >= 20
        and _numeric_feature(features, "a_calls_out_1h") >= 20
    ):
        scores[FraudScenario.MASS_CALLING] += 4
    if (
        _numeric_feature(features, "a_calls_out_24h") >= 30
        and _numeric_feature(features, "a_unique_contacts_out_24h") >= 25
    ):
        scores[FraudScenario.SIM_BOX] += 3
    if (
        _numeric_feature(features, "a_prior_unique_imsi_all_history") >= 4
        or _numeric_feature(features, "a_unique_imsis_24h") >= 4
    ):
        scores[FraudScenario.SIM_CLONE] += 5
    if call.call_type == CallType.FORWARDED:
        scores[FraudScenario.FORWARDING_CHAIN] += 2
        if (
            features["forwarding_chain_continuation_30s"]
            or features["a_prior_forwarding_motif_repeats_7d"]
        ):
            scores[FraudScenario.FORWARDING_CHAIN] += 3

    if len(recent) >= 5:
        contacts = {item.msisdn_b for item in recent}
        reciprocal = sum(
            any(
                other.msisdn_a == contact and other.msisdn_b == call.msisdn_a
                for other in history
            )
            for contact in contacts
        )
        if 5 <= len(contacts) <= 10 and reciprocal >= len(contacts) * 0.8:
            scores[FraudScenario.CALL_CAROUSEL] += 5

    scenario = max(scores, key=lambda item: scores[item])
    if scores[scenario] == 0:
        return (
            FraudScenario.MASS_CALLING
            if _numeric_feature(features, "a_unique_contacts_out_24h") >= 10
            else FraudScenario.WANGIRI
        )
    return scenario


def _numeric_feature(features: Mapping[str, FeatureValue], name: str) -> int | float:
    value = features[name]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    raise ValueError(f"Признак модели {name} должен быть числовым")


def _feature_description(feature: str, value: object) -> str:
    known = {
        "call_type": "Тип звонка",
        "duration_seconds": "Длительность звонка, секунд",
        "hour": "Час звонка",
        "day_of_week": "День недели звонка",
        "is_weekend": "Звонок в выходной день",
        "is_night": "Звонок в ночное время",
        "is_short_call": "Короткий звонок (до 10 секунд)",
        "is_zero_duration": "Звонок без соединения",
        "is_long_call": "Длительный звонок (от 5 минут)",
        "cross_prefix_call": "Номера относятся к разным телефонным префиксам",
        "has_forwarding": "В звонке используется переадресация",
        "forwarding_chain_length_proxy": "Число звеньев переадресации",
        "forwarding_chain_continuation_30s": "Звонок продолжает цепочку переадресации",
        "a_prior_unique_imsi_all_history": "Число SIM-карт, ранее связанных с номером звонящего",
        "a_prior_unique_contacts_all_history": "Число разных контактов номера звонящего",
        "b_prior_unique_contacts_all_history": "Число разных контактов номера абонента",
        "a_prior_graph_degree": "Число контактов номера звонящего",
        "b_prior_graph_degree": "Число контактов номера абонента",
        "a_b_prior_reciprocal_contact": "Были ли взаимные звонки между номерами",
        "a_prior_reciprocal_contact_count": "Число контактов с взаимными звонками",
        "a_prior_reciprocal_contact_rate": "Доля контактов с взаимными звонками",
        "a_prior_forwarding_motif_repeats_7d": "Повторение схемы переадресации за 7 дней",
        "a_b_prior_short_probe_then_long_call": "После короткой проверки был длительный звонок",
    }
    label = known.get(feature)
    if label is None:
        label = _windowed_feature_description(feature)
    if label is None:
        label = feature.replace("_", " ")
    return f"{label}: {_display_feature_value(value)}"


def _windowed_feature_description(feature: str) -> str | None:
    parts = feature.split("_")
    window = parts[-1] if parts[-1] in {"1h", "6h", "24h", "7d"} else None
    if window is None:
        return None

    prefix = parts[0]
    if prefix not in {"a", "b"}:
        return None
    owner = "звонящего" if prefix == "a" else "вызываемого абонента"
    metric = "_".join(parts[1:-1])
    labels = {
        "calls_total": "Всего звонков",
        "calls_out": "Исходящих звонков",
        "calls_in": "Входящих звонков",
        "unique_contacts_out": "Разных номеров для исходящих звонков",
        "unique_contacts_in": "Разных номеров для входящих звонков",
        "short_calls": "Коротких звонков (до 10 секунд)",
        "short_call_rate": "Доля коротких звонков",
        "zero_calls": "Звонков без соединения",
        "zero_call_rate": "Доля звонков без соединения",
        "long_call_rate": "Доля длительных звонков (от 5 минут)",
        "forwarded_calls": "Переадресованных звонков",
        "unique_imsis": "Разных SIM-карт",
        "unique_callers": "Разных звонивших номеров",
    }
    metric_label = labels.get(metric)
    if metric_label is None:
        return None
    window_label = {
        "1h": "за последний час",
        "6h": "за последние 6 часов",
        "24h": "за последние 24 часа",
        "7d": "за последние 7 дней",
    }[window]
    return f"{metric_label} у {owner} {window_label}"


def _display_feature_value(value: object) -> str:
    if isinstance(value, bool):
        return "да" if value else "нет"
    return str(value)
