from dataclasses import dataclass
from datetime import datetime


def _non_negative(*values: int) -> bool:
    return all(type(value) is int and value >= 0 for value in values)


@dataclass(frozen=True, slots=True)
class RiskDistribution:
    low: int
    medium: int
    high: int
    critical: int

    def __post_init__(self) -> None:
        if not _non_negative(self.low, self.medium, self.high, self.critical):
            raise ValueError("risk counts must be non-negative integers")


@dataclass(frozen=True, slots=True)
class TimelinePoint:
    timestamp: datetime
    total_calls: int
    suspicious_calls: int

    def __post_init__(self) -> None:
        if not _non_negative(self.total_calls, self.suspicious_calls):
            raise ValueError("timeline counts must be non-negative integers")
        if self.suspicious_calls > self.total_calls:
            raise ValueError("suspicious_calls cannot exceed total_calls")


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    total_calls: int
    analyzed_calls: int
    suspicious_calls: int
    suspicious_subscribers: int
    risk_distribution: RiskDistribution
    timeline: tuple[TimelinePoint, ...] = ()
    period_from: datetime | None = None
    period_to: datetime | None = None

    def __post_init__(self) -> None:
        counts = (
            self.total_calls,
            self.analyzed_calls,
            self.suspicious_calls,
            self.suspicious_subscribers,
            self.risk_distribution.low,
            self.risk_distribution.medium,
            self.risk_distribution.high,
            self.risk_distribution.critical,
        )
        if not _non_negative(*counts):
            raise ValueError("dashboard counts must be non-negative integers")
        if self.analyzed_calls > self.total_calls or self.suspicious_calls > self.analyzed_calls:
            raise ValueError("dashboard counts are inconsistent")
        if sum(counts[4:]) != self.analyzed_calls:
            raise ValueError("risk counts must sum to analyzed_calls")
        if self.period_from and self.period_to and self.period_to < self.period_from:
            raise ValueError("period_to must be greater than or equal to period_from")
