from app.domain.entities.subscriber import SubscriberProfile
from app.domain.repositories.subscribers import SubscriberRepository
from app.infrastructure.services.subscriber_service import (
    UnconfiguredSubscriberService,
)


class InfrastructureSubscriberRepository(SubscriberRepository):
    def __init__(self, service: UnconfiguredSubscriberService) -> None:
        self._service = service

    def get_profile(self, msisdn: str) -> SubscriberProfile | None:
        return self._service.get_profile(msisdn)
