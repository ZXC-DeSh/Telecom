from uuid import UUID

from pydantic import Field, model_validator

from app.api.schemas.calls import CDRCreate
from app.api.schemas.common import FraudScenario, Recommendation, RiskLevel, Schema
from app.api.schemas.prediction_reason import PredictionReason


class PredictionRequest(Schema):
    call_id: UUID | None = None
    call: CDRCreate | None = None

    @model_validator(mode="after")
    def require_call_source(self):
        if (self.call_id is None) == (self.call is None):
            raise ValueError("Provide exactly one of call_id or call")
        return self


class BatchPredictionRequest(Schema):
    calls: list[CDRCreate] = Field(min_length=1, max_length=1000)


class PredictionResult(Schema):
    call_id: UUID | None = None
    risk_score: float = Field(ge=0, le=1, allow_inf_nan=False)
    risk_level: RiskLevel
    is_fraud: bool
    fraud_scenario: FraudScenario | None = None
    reasons: list[PredictionReason] = Field(default_factory=list)
    recommendation: Recommendation
    auto_blocked: bool = False


class BatchPredictionResult(Schema):
    items: list[PredictionResult]
    total: int = Field(ge=0)
    processed: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_batch_counts(self):
        if self.processed > self.total:
            raise ValueError("processed cannot exceed total")
        if self.processed != len(self.items):
            raise ValueError("processed must match the number of result items")
        return self

