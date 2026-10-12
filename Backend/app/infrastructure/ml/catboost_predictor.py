import json
import logging
from datetime import datetime
from pathlib import Path

from catboost import CatBoostClassifier, Pool

from app.core.config import Settings
from app.domain.exceptions import FeatureUnavailable
from app.domain.entities.call import Call
from app.domain.entities.model_info import ModelInfo, ModelMetrics
from app.domain.entities.prediction import Prediction
from app.domain.repositories.calls import CallRepository
from app.domain.value_objects import Recommendation, RiskLevel
from app.infrastructure.ml.features import build_features, validate_feature_contract

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
            raise FileNotFoundError(f"Model file not found: {model_path}")

        model = CatBoostClassifier()
        model.load_model(str(model_path))

        self.model = model

    def _load_model_info(self, path: str | Path) -> None:
        info_path = Path(path)

        if not info_path.is_file():
            raise FileNotFoundError(f"Model metadata file not found: {info_path}")

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
            raise ValueError("model feature names must be unique")
        if "call_type" not in self._feature_names:
            raise ValueError("model feature names must include call_type")
        self._fraud_threshold = float(data.get("evaluation_threshold", 0.5))
        if not 0 < self._fraud_threshold < 1:
            raise ValueError("model evaluation_threshold must be between 0 and 1")

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
            raise FeatureUnavailable("CatBoost model is not available")
        if self._calls is None:
            raise FeatureUnavailable("Call history source is not configured")
        if not self._feature_names:
            raise FeatureUnavailable("Model feature names are not configured")

        raw_model_names = self.model.feature_names_
        model_names = tuple(raw_model_names) if raw_model_names is not None else ()
        if model_names and model_names != self._feature_names:
            raise FeatureUnavailable(
                "Model artifact feature names do not match its passport"
            )
        if self.model.get_cat_feature_indices():
            raise FeatureUnavailable(
                "Model expects categorical features, but the feature pipeline "
                "provides numeric features"
            )

        history = self._calls.history_before(call)
        features = build_features(call, history)
        try:
            values = validate_feature_contract(features, self._feature_names)
        except ValueError as exc:
            raise FeatureUnavailable(f"Invalid model feature contract: {exc}") from exc
        pool = Pool(
            data=[values],
            feature_names=list(self._feature_names),
        )
        probabilities = self.model.predict_proba(pool)[0]
        raw_classes = self.model.classes_
        if raw_classes is None:
            raise FeatureUnavailable("Model classes are not available")
        classes = tuple(raw_classes)
        positive_class_index = next(
            (index for index, label in enumerate(classes) if label in (1, True, "1")),
            None,
        )
        if positive_class_index is None:
            raise FeatureUnavailable("Model does not expose a positive fraud class")

        risk_score = float(probabilities[positive_class_index])
        risk_level = _risk_level(risk_score)
        return Prediction(
            call_id=call.id,
            risk_score=risk_score,
            risk_level=risk_level,
            is_fraud=risk_score >= self._fraud_threshold,
            recommendation=_recommendation(risk_level),
        )

    def get_info(self) -> ModelInfo:
        if self.model_passport is None:
            raise FeatureUnavailable("Model metadata is not configured")

        return self.model_passport


def _risk_level(score: float) -> RiskLevel:
    # Risk bands are presentation buckets; fraud classification uses the
    # threshold stored in the model passport above.
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
