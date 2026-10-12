from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from app.api.schemas.common import (
    CDRNumber,
    FraudScenario,
    Recommendation,
    RiskLevel,
    Schema,
    validate_date_range,
    validate_naive_datetime,
)
from app.api.schemas.prediction_reason import PredictionReason


class FraudAlertFilters(Schema):
    risk_level: RiskLevel | None = None
    fraud_scenario: FraudScenario | None = None
    msisdn: CDRNumber | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.date_from and self.date_to:
            validate_date_range(self.date_from, self.date_to)
        if self.date_from:
            validate_naive_datetime(self.date_from)
        if self.date_to:
            validate_naive_datetime(self.date_to)
        return self


class FraudAlert(Schema):
    alert_id: int = Field(ge=1)
    call_id: UUID
    call_time: datetime
    msisdn_a: CDRNumber
    msisdn_b: CDRNumber
    duration_seconds: float = Field(ge=0, allow_inf_nan=False)
    risk_score: float = Field(ge=0, le=1, allow_inf_nan=False)
    risk_level: RiskLevel
    fraud_scenario: FraudScenario | None = None
    reasons: list[PredictionReason] = Field(default_factory=list)
    recommendation: Recommendation
    auto_blocked: bool = False

    @model_validator(mode="after")
    def validate_call_time(self):
        validate_naive_datetime(self.call_time)
        return self


class FraudAlertList(Schema):
    items: list[FraudAlert]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    pages: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_page_count(self):
        expected_pages = (self.total + self.page_size - 1) // self.page_size
        if self.pages != expected_pages:
            raise ValueError("pages must match total and page_size")
        return self
