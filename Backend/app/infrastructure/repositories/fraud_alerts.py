from app.domain.entities.fraud_alert import FraudAlertPage
from app.domain.entities.search import FraudAlertSearchCriteria
from app.domain.repositories.fraud_alerts import FraudAlertRepository
from app.infrastructure.services.fraud_alerts import FraudAlertService


class FraudAlertRepositoryAdapter(FraudAlertRepository):
    def __init__(self, service: FraudAlertService) -> None:
        self._service = service

    def list(self, criteria: FraudAlertSearchCriteria) -> FraudAlertPage:
        return self._service.list(criteria)
