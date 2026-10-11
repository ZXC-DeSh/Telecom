from datetime import datetime

from pydantic import Field

from app.api.schemas.common import Schema


class RiskDistribution(Schema):
    low: int = Field(ge=0)
    medium: int = Field(ge=0)
    high: int = Field(ge=0)
    critical: int = Field(ge=0)


class TimelinePoint(Schema):
    timestamp: datetime
    total_calls: int = Field(ge=0)
    suspicious_calls: int = Field(ge=0)


class DashboardSummary(Schema):
    period_from: datetime | None = None
    period_to: datetime | None = None
    total_calls: int = Field(ge=0)
    analyzed_calls: int = Field(ge=0)
    suspicious_calls: int = Field(ge=0)
    suspicious_subscribers: int = Field(ge=0)
    risk_distribution: RiskDistribution
    timeline: list[TimelinePoint] = Field(default_factory=list)
