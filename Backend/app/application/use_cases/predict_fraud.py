from app.application.exceptions import EntityNotFound
from app.domain.entities.call import Call
from app.domain.entities.prediction import Prediction
from app.domain.repositories.call_repository import CallRepository
from app.domain.repositories.model_repository import FraudModel


class PredictFraud:
    """Application use case; prediction requires a configured model adapter."""

    def __init__(self, predictor: FraudModel, calls: CallRepository):
        self._predictor = predictor
        self._calls = calls

    def execute(self, call_id: int | None = None, call: Call | None = None) -> Prediction:
        if (call_id is None) == (call is None):
            raise ValueError("provide exactly one of call_id or call")
        if call_id is not None:
            call = self._calls.get_by_id(call_id)
            if call is None:
                raise EntityNotFound(f"Call {call_id} was not found")
        return self._predictor.predict(call)

    def execute_batch(self, calls: tuple[Call, ...]) -> tuple[Prediction, ...]:
        if not calls:
            raise ValueError("at least one call is required")
        if len(calls) > 1000:
            raise ValueError("no more than 1000 calls may be scored at once")
        return tuple(self._predictor.predict(call) for call in calls)
