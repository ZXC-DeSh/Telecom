from app.domain.entities.fraud_alert import FraudAlertPage
from app.domain.entities.search import FraudAlertSearchCriteria
from app.domain.repositories.fraud_alert_repository import FraudAlertRepository


class ListFraudAlerts:
    def __init__(self, alerts: FraudAlertRepository):
        self._alerts = alerts

    def execute(self, criteria: FraudAlertSearchCriteria) -> FraudAlertPage:
        return self._alerts.list(criteria)
