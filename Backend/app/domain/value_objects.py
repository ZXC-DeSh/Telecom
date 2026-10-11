from enum import StrEnum


class CallType(StrEnum):
    INCOMING = "01"
    OUTGOING = "02"
    FORWARDED = "03"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FraudScenario(StrEnum):
    WANGIRI = "S1"
    MASS_CALLING = "S2"
    SIM_BOX = "S3"
    SIM_CLONE = "S4"
    FORWARDING_CHAIN = "S5"
    CALL_CAROUSEL = "S6"
    VISHING_SPOOFING = "S7"


class Recommendation(StrEnum):
    MONITOR = "monitor"
    MANUAL_REVIEW = "manual_review"
    ESCALATE = "escalate"


class AnalysisStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
