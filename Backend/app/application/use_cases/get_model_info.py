from app.domain.entities.model_info import ModelInfo
from app.domain.repositories.models import ModelInfoRepository


class GetModelInfo:
    def __init__(self, models: ModelInfoRepository):
        self._models = models

    def execute(self) -> ModelInfo:
        return self._models.get_info()
