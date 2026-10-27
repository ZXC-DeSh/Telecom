from dataclasses import replace
from uuid import UUID

from app.application.exceptions import EntityNotFound
from app.domain.entities.call import Call
from app.domain.entities.prediction import Prediction
from app.domain.repositories.calls import CallRepository
from app.domain.repositories.models import CallRiskAssessmentRepository, FraudModel


class PredictFraud:
    def __init__(
        self,
        predictor: FraudModel,
        calls: CallRepository,
        assessments: CallRiskAssessmentRepository,
    ):
        self._predictor = predictor
        self._calls = calls
        self._assessments = assessments

    def execute(
        self, call_id: UUID | None = None, call: Call | None = None
    ) -> Prediction:
        if (call_id is None) == (call is None):
            raise ValueError("укажите ровно одно из полей call_id или call")
        if call_id is not None:
            call = self._calls.get_by_id(call_id)
            if call is None:
                raise EntityNotFound(f"Вызов с идентификатором {call_id} не найден")
        if call is None:
            raise EntityNotFound(f"Вызов с идентификатором {call_id} не найден")

        prediction = self._predictor.predict(call)
        if call.id is None:
            return prediction
        if prediction.call_id != call.id:
            prediction = replace(prediction, call_id=call.id)
        model = self._predictor.get_info()
        self._assessments.save(call.id, prediction, model)
        return prediction

    def execute_batch(self, calls: tuple[Call, ...]) -> tuple[Prediction, ...]:
        if not calls:
            raise ValueError("необходимо указать хотя бы один вызов")
        if len(calls) > 1000:
            raise ValueError("за один раз можно оценить не более 1000 вызовов")
        return tuple(self._predictor.predict(call) for call in calls)
