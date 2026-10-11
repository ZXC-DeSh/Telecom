from typing import Protocol

from app.domain.entities.call import Call
from app.domain.entities.model_info import ModelInfo
from app.domain.entities.prediction import Prediction


class ModelInfoRepository(Protocol):
    def get_info(self) -> ModelInfo: ...


class ModelReadiness(Protocol):
    def is_available(self) -> bool: ...


class FraudModel(ModelReadiness, Protocol):
    def predict(self, call: Call) -> Prediction: ...
