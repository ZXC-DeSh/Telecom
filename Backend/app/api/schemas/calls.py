from datetime import datetime
from math import ceil
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.api.schemas.common import (
    CallType,
    CDRNumber,
    FraudScenario,
    Recommendation,
    RiskLevel,
    Schema,
    validate_date_range,
    validate_naive_datetime,
)
from app.api.schemas.prediction_reason import PredictionReason


class CallFilters(Schema):
    date_from: datetime | None = None
    date_to: datetime | None = None
    call_type: CallType | None = None
    msisdn: CDRNumber | None = None
    risk_level: RiskLevel | None = None
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


class CDRCreate(Schema):
    call_type: CallType
    imsi_a: str | None = Field(default=None, min_length=1, max_length=32)
    msisdn_a: CDRNumber
    msisdn_b: CDRNumber
    call_time: datetime
    duration_seconds: float = Field(ge=0, allow_inf_nan=False)
    msisdn_c: CDRNumber | None = None

    @field_validator("call_time", mode="before")
    @classmethod
    def parse_cdr_call_time(cls, value):
        if isinstance(value, str) and len(value) == 14 and value.isdigit():
            try:
                return datetime.strptime(value, "%Y%m%d%H%M%S")
            except ValueError as exc:
                raise ValueError(
                    "call_time должен быть корректной временной меткой в формате yyyyMMddHHmmss"
                ) from exc
        return value

    @model_validator(mode="after")
    def validate_forwarding_number(self):
        if self.call_type == CallType.FORWARDED and self.msisdn_c is None:
            raise ValueError(
                "для переадресованного вызова (call_type='03') требуется msisdn_c"
            )
        if self.call_type != CallType.FORWARDED and self.msisdn_c is not None:
            raise ValueError(
                "msisdn_c допустим только для переадресованного вызова (call_type='03')"
            )
        return self

    @model_validator(mode="after")
    def validate_call_time(self):
        validate_naive_datetime(self.call_time)
        return self


class CallRecord(Schema):
    id: UUID
    call_type: CallType
    imsi_a: str | None = Field(default=None, min_length=1, max_length=32)
    msisdn_a: CDRNumber
    msisdn_b: CDRNumber
    call_time: datetime
    duration_seconds: float = Field(ge=0, allow_inf_nan=False)
    msisdn_c: CDRNumber | None = None

    @model_validator(mode="after")
    def validate_call_time(self):
        validate_naive_datetime(self.call_time)
        return self


class CallListItem(CallRecord):
    risk_score: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    risk_level: RiskLevel | None = None
    is_fraud: bool | None = None
    fraud_scenario: FraudScenario | None = None


class CallDetail(CallListItem):
    operator_a: str | None = None
    operator_b: str | None = None
    operator_c: str | None = None
    reasons: list[PredictionReason] = Field(default_factory=list)
    recommendation: Recommendation | None = None
    operator_message: str | None = None


class CallListData(Schema):
    items: list[CallListItem]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    pages: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_page_count(self):
        expected_pages = ceil(self.total / self.page_size) if self.total else 0
        if self.pages != expected_pages:
            raise ValueError("число страниц должно соответствовать total и page_size")
        return self
