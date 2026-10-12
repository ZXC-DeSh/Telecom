from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.value_objects import AnalysisStatus


@dataclass(frozen=True, slots=True)
class AnalysisMetrics:
    total_calls: int
    processed_calls: int
    fraud_calls: int
    low_risk_calls: int
    medium_risk_calls: int
    high_risk_calls: int
    critical_risk_calls: int

    def __post_init__(self) -> None:
        values = (
            self.total_calls,
            self.processed_calls,
            self.fraud_calls,
            self.low_risk_calls,
            self.medium_risk_calls,
            self.high_risk_calls,
            self.critical_risk_calls,
        )
        if any(value < 0 for value in values):
            raise ValueError("analysis metrics cannot be negative")
        if self.processed_calls > self.total_calls or self.fraud_calls > self.processed_calls:
            raise ValueError("analysis metrics counts are inconsistent")
        risk_count = sum(values[3:])
        if risk_count != self.processed_calls:
            raise ValueError("risk counts must sum to processed_calls")


@dataclass(frozen=True, slots=True)
class AnalysisJob:
    job_id: UUID
    status: AnalysisStatus
    date_from: datetime
    date_to: datetime
    created_at: datetime
    progress_percent: float = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metrics: AnalysisMetrics | None = None
    error: str | None = None
    force_recalculate: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", AnalysisStatus(self.status))
        if self.date_to < self.date_from:
            raise ValueError("date_to must be greater than or equal to date_from")
        if not 0 <= self.progress_percent <= 100:
            raise ValueError("progress_percent must be between 0 and 100")
        if self.metrics is not None and self.metrics.total_calls < 0:
            raise ValueError("total_calls cannot be negative")
