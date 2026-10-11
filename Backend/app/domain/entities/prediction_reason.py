from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PredictionReason:
    feature: str
    impact: str
    value: str | int | float | bool | None = None
    contribution: float | None = None
    description: str | None = None
