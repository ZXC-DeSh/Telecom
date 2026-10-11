from app.domain.entities.health import ServiceHealth
from app.domain.repositories.health_repository import DatabaseReadiness
from app.domain.repositories.model_repository import ModelReadiness


class CheckServiceHealth:
    def __init__(self, database: DatabaseReadiness, model: ModelReadiness):
        self._database = database
        self._model = model

    def execute(self) -> ServiceHealth:
        return ServiceHealth(
            database_available=self._check(self._database.is_database_available),
            model_available=self._check(self._model.is_available),
        )

    @staticmethod
    def _check(check):
        try:
            return bool(check())
        except Exception:
            return False
