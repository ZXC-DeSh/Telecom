from dataclasses import dataclass
from datetime import datetime
from math import isfinite


@dataclass(frozen=True, slots=True)
class ModelMetrics:
    precision: float | None = None
    recall: float | None = None
    f1_score: float | None = None
    pr_auc: float | None = None
    false_positive_rate: float | None = None

    def __post_init__(self) -> None:
        for metric in (
            self.precision,
            self.recall,
            self.f1_score,
            self.pr_auc,
            self.false_positive_rate,
        ):
            if metric is not None and (not isfinite(metric) or not 0 <= metric <= 1):
                raise ValueError("метрики модели должны быть от 0 до 1")


@dataclass(frozen=True, slots=True)
class ModelInfo:
    name: str
    version: str
    is_loaded: bool
    algorithm: str = "CatBoost"
    trained_at: datetime | None = None
    feature_names: tuple[str, ...] = ()
    metrics: ModelMetrics | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.version or not self.algorithm:
            raise ValueError("необходимо указать имя, версию и алгоритм модели")
