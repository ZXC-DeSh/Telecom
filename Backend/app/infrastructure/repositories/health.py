from app.domain.repositories.health import (
    DatabaseReadinessRepository,
    ModelReadinessRepository,
)
from app.infrastructure.ml.catboost_predictor import CatBoostPredictor
from app.infrastructure.services.database_health_service import (
    PostgresDatabaseHealthService,
)


class DatabaseHealthRepository(DatabaseReadinessRepository):
    def __init__(self, service: PostgresDatabaseHealthService) -> None:
        self._service = service

    def is_database_available(self) -> bool:
        return self._service.is_database_available()


class ModelHealthRepository(ModelReadinessRepository):
    def __init__(self, service: CatBoostPredictor) -> None:
        self._service = service

    def is_available(self) -> bool:
        return self._service.is_available()
