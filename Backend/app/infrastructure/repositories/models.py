from uuid import UUID

from app.domain.entities.call import Call
from app.domain.entities.model_info import ModelInfo
from app.domain.entities.prediction import Prediction
from app.domain.repositories.models import (
    CallRiskAssessmentRepository,
    FraudModel,
    ModelInfoRepository,
)
from app.infrastructure.ml.catboost_predictor import CatBoostPredictor
from app.infrastructure.services.call_risk_assessment_service import (
    PostgresCallRiskAssessmentService,
)


class CatBoostRepository(FraudModel, ModelInfoRepository):
    def __init__(self, service: CatBoostPredictor) -> None:
        self._service = service

    def predict(self, call: Call) -> Prediction:
        return self._service.predict(call)

    def get_info(self) -> ModelInfo:
        return self._service.get_info()


class PostgresCallRiskAssessmentRepository(CallRiskAssessmentRepository):
    def __init__(self, service: PostgresCallRiskAssessmentService) -> None:
        self._service = service

    def save(self, call_id: UUID, prediction: Prediction, model: ModelInfo) -> None:
        self._service.save(call_id, prediction, model)

