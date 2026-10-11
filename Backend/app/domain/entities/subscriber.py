from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from app.domain.value_objects import RiskLevel


@dataclass(frozen=True, slots=True)
class SubscriberStatistics:
    total_calls: int
    incoming_calls: int
    outgoing_calls: int
    forwarded_calls: int
    unique_contacts: int
    short_calls: int
    unanswered_calls: int
    short_calls_ratio: float
    unanswered_calls_ratio: float

    def __post_init__(self) -> None:
        counts = (
            self.total_calls,
            self.incoming_calls,
            self.outgoing_calls,
            self.forwarded_calls,
            self.unique_contacts,
            self.short_calls,
            self.unanswered_calls,
        )
        if any(type(count) is not int or count < 0 for count in counts):
            raise ValueError("subscriber counts must be non-negative integers")
        if self.incoming_calls + self.outgoing_calls + self.forwarded_calls != self.total_calls:
            raise ValueError("call direction counts must sum to total_calls")
        if self.short_calls > self.total_calls or self.unanswered_calls > self.total_calls:
            raise ValueError("call subsets cannot exceed total_calls")
        for ratio in (self.short_calls_ratio, self.unanswered_calls_ratio):
            if not isfinite(ratio) or not 0 <= ratio <= 1:
                raise ValueError("subscriber ratios must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class SubscriberContact:
    msisdn: str
    calls_count: int
    risk_score: float | None = None
    risk_level: RiskLevel | None = None


@dataclass(frozen=True, slots=True)
class SubscriberActivityPoint:
    timestamp: datetime
    calls_count: int


@dataclass(frozen=True, slots=True)
class SubscriberProfile:
    msisdn: str
    statistics: SubscriberStatistics
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    risk_score: float | None = None
    risk_level: RiskLevel | None = None
    contacts: tuple[SubscriberContact, ...] = ()
    activity: tuple[SubscriberActivityPoint, ...] = ()
    related_suspicious_numbers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if len(self.msisdn) != 10 or not self.msisdn.isascii() or not self.msisdn.isdigit():
            raise ValueError("msisdn must contain 10 digits")
        if self.first_seen_at and self.last_seen_at and self.last_seen_at < self.first_seen_at:
            raise ValueError("last_seen_at cannot precede first_seen_at")
        if self.risk_score is not None and (
            not isfinite(self.risk_score) or not 0 <= self.risk_score <= 1
        ):
            raise ValueError("risk_score must be between 0 and 1")
