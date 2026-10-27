from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from uuid import UUID

from app.domain.entities.page import Page
from app.domain.entities.prediction_reason import PredictionReason
from app.domain.value_objects import FraudScenario, Recommendation, RiskLevel


@dataclass(frozen=True, slots=True)
class FraudAlert:
    alert_id: int
    call_id: UUID
    call_time: datetime
    msisdn_a: str
    msisdn_b: str
    duration_seconds: float
    risk_score: float
    risk_level: RiskLevel
    recommendation: Recommendation
    fraud_scenario: FraudScenario | None = None
    reasons: tuple[PredictionReason, ...] = ()
    auto_blocked: bool = False

    def __post_init__(self) -> None:
        if type(self.alert_id) is not int or self.alert_id < 1:
            raise ValueError("alert_id должен быть положительным целым числом")
        if not isinstance(self.call_id, UUID):
            raise TypeError("call_id должен быть UUID")
        if not 0 <= self.risk_score <= 1 or not isfinite(self.risk_score):
            raise ValueError("risk_score должен быть конечным числом от 0 до 1")
        if self.duration_seconds < 0 or not isfinite(self.duration_seconds):
            raise ValueError(
                "duration_seconds должен быть конечным неотрицательным числом"
            )
        if any(
            len(number) != 10 or not number.isascii() or not number.isdigit()
            for number in (self.msisdn_a, self.msisdn_b)
        ):
            raise ValueError("номера в уведомлении должны содержать 10 цифр")
        object.__setattr__(self, "risk_level", RiskLevel(self.risk_level))
        object.__setattr__(self, "recommendation", Recommendation(self.recommendation))
        if self.fraud_scenario is not None:
            object.__setattr__(
                self, "fraud_scenario", FraudScenario(self.fraud_scenario)
            )

    @property
    def operator_message(self) -> str:
        from app.domain.entities.prediction import operator_message_for

        return operator_message_for(self.risk_level)


FraudAlertPage = Page[FraudAlert]
