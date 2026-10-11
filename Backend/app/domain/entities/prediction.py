from dataclasses import dataclass
from math import isfinite

from app.domain.entities.prediction_reason import PredictionReason
from app.domain.value_objects import FraudScenario, Recommendation, RiskLevel


@dataclass(frozen=True, slots=True)
class Prediction:
    call_id: int | None
    risk_score: float
    risk_level: RiskLevel
    is_fraud: bool
    fraud_scenario: FraudScenario | None = None
    recommendation: Recommendation = Recommendation.MONITOR
    reasons: tuple[PredictionReason, ...] = ()
    auto_blocked: bool = False

    def __post_init__(self) -> None:
        if self.call_id is not None and (
            type(self.call_id) is not int
            or not 1 <= self.call_id <= 9_223_372_036_854_775_807
        ):
            raise ValueError("call_id must be a positive integer")
        if (
            isinstance(self.risk_score, bool)
            or not isinstance(self.risk_score, (int, float))
            or not isfinite(self.risk_score)
            or not 0 <= self.risk_score <= 1
        ):
            raise ValueError("risk_score must be finite and between 0 and 1")
        if not isinstance(self.is_fraud, bool):
            raise ValueError("is_fraud must be a boolean")
        if not isinstance(self.auto_blocked, bool):
            raise ValueError("auto_blocked must be a boolean")
        if any(not reason.feature or not reason.impact for reason in self.reasons):
            raise ValueError("prediction reason feature and impact are required")
        object.__setattr__(self, "risk_level", RiskLevel(self.risk_level))
        if self.fraud_scenario is not None:
            object.__setattr__(self, "fraud_scenario", FraudScenario(self.fraud_scenario))
        object.__setattr__(self, "recommendation", Recommendation(self.recommendation))
