from collections.abc import Callable

from app.domain.entities.health import ServiceHealth
from app.domain.repositories.health import (
    DatabaseReadinessRepository,
    ModelReadinessRepository,
)


class CheckServiceHealth:
    def __init__(
        self,
        database: DatabaseReadinessRepository,
        model: ModelReadinessRepository,
    ) -> None:
        self._database = database
        self._model = model

    def execute(self) -> ServiceHealth:
        return ServiceHealth(
            database_available=self._check(self._database.is_database_available),
            model_available=self._check(self._model.is_available),
        )

    @staticmethod
    def _check(check: Callable[[], bool]) -> bool:
        try:
            return bool(check())
        except Exception:
            return False
