from datetime import datetime

from pydantic import Field

from app.api.schemas.common import Schema


class ModelMetrics(Schema):
    precision: float | None = Field(default=None, ge=0, le=1)
    recall: float | None = Field(default=None, ge=0, le=1)
    f1_score: float | None = Field(default=None, ge=0, le=1)
    pr_auc: float | None = Field(default=None, ge=0, le=1)
    false_positive_rate: float | None = Field(default=None, ge=0, le=1)


class ModelInfo(Schema):
    name: str
    version: str
    algorithm: str = "CatBoost"
    trained_at: datetime | None = None
    feature_names: list[str] = Field(default_factory=list)
    metrics: ModelMetrics | None = None
    is_loaded: bool
