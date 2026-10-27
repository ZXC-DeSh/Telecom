from dataclasses import dataclass
from math import isfinite
from uuid import UUID

from app.domain.entities.prediction_reason import PredictionReason
from app.domain.value_objects import FraudScenario, Recommendation, RiskLevel


@dataclass(frozen=True, slots=True)
class Prediction:
    call_id: UUID | None
    risk_score: float
    risk_level: RiskLevel
    is_fraud: bool
    fraud_scenario: FraudScenario | None = None
    recommendation: Recommendation = Recommendation.MONITOR
    reasons: tuple[PredictionReason, ...] = ()
    auto_blocked: bool = False

    def __post_init__(self) -> None:
        if self.call_id is not None and not isinstance(self.call_id, UUID):
            raise ValueError("call_id должен быть UUID")
        if (
            isinstance(self.risk_score, bool)
            or not isinstance(self.risk_score, (int, float))
            or not isfinite(self.risk_score)
            or not 0 <= self.risk_score <= 1
        ):
            raise ValueError("risk_score должен быть конечным числом от 0 до 1")
        if not isinstance(self.is_fraud, bool):
            raise TypeError("is_fraud должен быть логическим значением")
        if not isinstance(self.auto_blocked, bool):
            raise TypeError("auto_blocked должен быть логическим значением")
        if any(not reason.feature or not reason.impact for reason in self.reasons):
            raise ValueError(
                "для причины прогноза необходимо указать признак и влияние"
            )
        object.__setattr__(self, "risk_level", RiskLevel(self.risk_level))
        if self.fraud_scenario is not None:
            object.__setattr__(
                self, "fraud_scenario", FraudScenario(self.fraud_scenario)
            )
        object.__setattr__(self, "recommendation", Recommendation(self.recommendation))

    @property
    def operator_message(self) -> str:
        return operator_message_for(self.risk_level)


def operator_message_for(level: RiskLevel) -> str:
    if level == RiskLevel.LOW:
        return (
            "Сообщите абоненту, что признаков повышенного риска не выявлено. "
            "Напомните не сообщать по телефону коды из SMS, пароли и данные карты."
        )
    if level == RiskLevel.MEDIUM:
        return (
            "Предупредите абонента о настораживающих признаках. Попросите не "
            "сообщать коды из SMS, пароли и данные карты; при сомнениях завершить "
            "звонок и самостоятельно связаться с организацией по официальному номеру."
        )
    return (
        "Предупредите абонента о высоком риске мошенничества. Посоветуйте не "
        "сообщать коды из SMS, пароли и данные карты, завершить подозрительный "
        "разговор и самостоятельно связаться с организацией по официальному номеру."
    )
