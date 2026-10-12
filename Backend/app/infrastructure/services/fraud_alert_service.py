from app.domain.entities.fraud_alert import FraudAlertPage
from app.domain.entities.search import FraudAlertSearchCriteria
from app.domain.exceptions import FeatureUnavailable


class UnconfiguredFraudAlertService:
    def list(self, criteria: FraudAlertSearchCriteria) -> FraudAlertPage:
        raise FeatureUnavailable("Fraud alert query source is not configured")
