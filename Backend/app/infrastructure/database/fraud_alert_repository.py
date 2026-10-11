from app.application.exceptions import FeatureUnavailable
from app.domain.entities.fraud_alert import FraudAlertPage
from app.domain.entities.search import FraudAlertSearchCriteria


class UnconfiguredFraudAlertRepository:
    def list(self, criteria: FraudAlertSearchCriteria) -> FraudAlertPage:
        raise FeatureUnavailable("Fraud alert query source is not configured")
