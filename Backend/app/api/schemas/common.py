from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.domain.value_objects import (
    AnalysisStatus,
    CallType,
    FraudScenario,
    Recommendation,
    RiskLevel,
)

__all__ = [
    "AnalysisStatus",
    "CallType",
    "CDRNumber",
    "FraudScenario",
    "PhoneNumber",
    "Recommendation",
    "RiskLevel",
    "Schema",
    "validate_date_range",
    "validate_naive_datetime",
]


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


PhoneNumber = Annotated[
    str,
    StringConstraints(min_length=1, max_length=20),
]
CDRNumber = Annotated[str, StringConstraints(pattern=r"^[0-9]{10}$")]


def validate_naive_datetime(value: datetime) -> None:
    if value.utcoffset() is not None:
        raise ValueError("datetime must not include a timezone")


def validate_date_range(date_from: datetime, date_to: datetime) -> None:
    start_is_aware = date_from.utcoffset() is not None
    end_is_aware = date_to.utcoffset() is not None
    if start_is_aware != end_is_aware:
        raise ValueError("date_from and date_to must both be timezone-aware or naive")
    if date_to < date_from:
        raise ValueError("date_to must be greater than or equal to date_from")


class PaginatedResponse(Schema):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    items: list[object]


class DateRangeRequest(Schema):
    date_from: datetime
    date_to: datetime

    @model_validator(mode="after")
    def validate_date_range(self):
        validate_date_range(self.date_from, self.date_to)
        return self
