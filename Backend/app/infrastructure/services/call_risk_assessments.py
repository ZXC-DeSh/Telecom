from dataclasses import asdict
from uuid import UUID

from psycopg2.extras import Json

from app.domain.entities.model_info import ModelInfo
from app.domain.entities.prediction import Prediction
from app.infrastructure.database.connection import Database


class CallRiskAssessmentService:
    def __init__(self, database: Database) -> None:
        self._database = database

    def save(self, call_id: UUID, prediction: Prediction, model: ModelInfo) -> None:
        reasons = Json([asdict(reason) for reason in prediction.reasons])
        self._database.insert(
            "public.call_risk_assessments",
            {
                "call_id": call_id,
                "model_name": model.name,
                "model_version": model.version,
                "risk_score": prediction.risk_score,
                "risk_level": prediction.risk_level.value,
                "is_fraud": prediction.is_fraud,
                "fraud_scenario": prediction.fraud_scenario.value
                if prediction.fraud_scenario is not None
                else None,
                "reasons": reasons,
                "recommendation": prediction.recommendation.value,
                "auto_blocked": prediction.auto_blocked,
            },
        )
