from datetime import datetime

from pydantic import Field, model_validator

from app.api.schemas.common import CDRNumber, RiskLevel, Schema


class SubscriberStatistics(Schema):
    total_calls: int = Field(ge=0)
    incoming_calls: int = Field(ge=0)
    outgoing_calls: int = Field(ge=0)
    forwarded_calls: int = Field(ge=0)
    unique_contacts: int = Field(ge=0)
    short_calls: int = Field(ge=0)
    unanswered_calls: int = Field(ge=0)
    short_calls_ratio: float = Field(ge=0, le=1, allow_inf_nan=False)
    unanswered_calls_ratio: float = Field(ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_counts(self):
        direction_count = self.incoming_calls + self.outgoing_calls + self.forwarded_calls
        if direction_count != self.total_calls:
            raise ValueError("call direction counts must sum to total_calls")
        if self.short_calls > self.total_calls or self.unanswered_calls > self.total_calls:
            raise ValueError("call subsets cannot exceed total_calls")
        return self


class SubscriberContact(Schema):
    msisdn: CDRNumber
    calls_count: int = Field(ge=0)
    risk_score: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    risk_level: RiskLevel | None = None


class SubscriberActivityPoint(Schema):
    timestamp: datetime
    calls_count: int = Field(ge=0)


class SubscriberProfile(Schema):
    msisdn: CDRNumber
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    risk_score: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    risk_level: RiskLevel | None = None
    statistics: SubscriberStatistics
    contacts: list[SubscriberContact] = Field(default_factory=list)
    activity: list[SubscriberActivityPoint] = Field(default_factory=list)
    related_suspicious_numbers: list[CDRNumber] = Field(default_factory=list)
