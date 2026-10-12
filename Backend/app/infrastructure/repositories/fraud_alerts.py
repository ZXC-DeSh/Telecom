from app.domain.entities.fraud_alert import FraudAlertPage
from app.domain.entities.search import FraudAlertSearchCriteria
from app.domain.repositories.fraud_alerts import FraudAlertRepository
from app.infrastructure.services.fraud_alert_service import (
    UnconfiguredFraudAlertService,
)


class InfrastructureFraudAlertRepository(FraudAlertRepository):
    def __init__(self, service: UnconfiguredFraudAlertService) -> None:
        self._service = service

    def list(self, criteria: FraudAlertSearchCriteria) -> FraudAlertPage:
        return self._service.list(criteria)
