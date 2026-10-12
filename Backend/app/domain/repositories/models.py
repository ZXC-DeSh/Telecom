from typing import Protocol
from uuid import UUID

from app.domain.entities.call import Call
from app.domain.entities.model_info import ModelInfo
from app.domain.entities.prediction import Prediction


class ModelInfoRepository(Protocol):
    def get_info(self) -> ModelInfo: ...


class FraudModel(Protocol):
    def predict(self, call: Call) -> Prediction: ...

    def get_info(self) -> ModelInfo: ...


class CallRiskAssessmentRepository(Protocol):
    def save(self, call_id: UUID, prediction: Prediction, model: ModelInfo) -> None: ...
