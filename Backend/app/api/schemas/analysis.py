from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from app.api.schemas.common import (
    AnalysisStatus,
    Schema,
    validate_date_range,
    validate_naive_datetime,
)


class AnalysisRunRequest(Schema):
    date_from: datetime
    date_to: datetime
    force_recalculate: bool = False

    @model_validator(mode="after")
    def validate_date_range(self):
        validate_date_range(self.date_from, self.date_to)
        validate_naive_datetime(self.date_from)
        validate_naive_datetime(self.date_to)
        return self


class AnalysisJobAccepted(Schema):
    job_id: UUID
    status: AnalysisStatus = AnalysisStatus.QUEUED
    date_from: datetime
    date_to: datetime
    created_at: datetime


class AnalysisMetrics(Schema):
    total_calls: int = Field(ge=0)
    processed_calls: int = Field(ge=0)
    fraud_calls: int = Field(ge=0)
    low_risk_calls: int = Field(ge=0)
    medium_risk_calls: int = Field(ge=0)
    high_risk_calls: int = Field(ge=0)
    critical_risk_calls: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self):
        risk_count = (
            self.low_risk_calls
            + self.medium_risk_calls
            + self.high_risk_calls
            + self.critical_risk_calls
        )
        if self.processed_calls > self.total_calls:
            raise ValueError("processed_calls cannot exceed total_calls")
        if self.fraud_calls > self.processed_calls:
            raise ValueError("fraud_calls cannot exceed processed_calls")
        if risk_count != self.processed_calls:
            raise ValueError("risk counts must sum to processed_calls")
        return self


class AnalysisJobStatus(Schema):
    job_id: UUID
    status: AnalysisStatus
    progress_percent: float = Field(ge=0, le=100)
    date_from: datetime
    date_to: datetime
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metrics: AnalysisMetrics | None = None
    error: str | None = None
