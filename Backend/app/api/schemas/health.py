from typing import Literal

from pydantic import Field

from app.api.schemas.common import Schema


class DependencyHealth(Schema):
    status: Literal["ok", "degraded", "unavailable"]
    message: str | None = None


class HealthData(Schema):
    status: Literal["ok", "degraded", "unavailable"]
    database: DependencyHealth
    model: DependencyHealth


class HealthResponse(Schema):
    status_code: int = Field(ge=100, le=599)
    message: str
    data: HealthData
