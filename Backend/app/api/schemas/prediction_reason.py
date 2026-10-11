from pydantic import Field

from app.api.schemas.common import Schema


class PredictionReason(Schema):
    feature: str = Field(min_length=1)
    value: str | int | float | bool | None = None
    impact: str = Field(min_length=1)
    contribution: float | None = None
    description: str | None = None
