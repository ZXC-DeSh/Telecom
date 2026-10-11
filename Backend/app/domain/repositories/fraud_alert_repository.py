from typing import Protocol

from app.domain.entities.fraud_alert import FraudAlertPage
from app.domain.entities.search import FraudAlertSearchCriteria


class FraudAlertRepository(Protocol):
    def list(self, criteria: FraudAlertSearchCriteria) -> FraudAlertPage: ...
