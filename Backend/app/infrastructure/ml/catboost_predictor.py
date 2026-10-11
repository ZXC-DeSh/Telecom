

from app.application.exceptions import FeatureUnavailable
from app.domain.entities.call import Call
from app.domain.entities.model_info import ModelInfo
from app.domain.entities.prediction import Prediction


class CatBoostPredictor:
    def is_available(self) -> bool:
        return False

    def predict(self, call: Call) -> Prediction:
        raise FeatureUnavailable("The model feature pipeline is not configured")

    def get_info(self) -> ModelInfo:
        raise FeatureUnavailable("Model metadata is not configured")
