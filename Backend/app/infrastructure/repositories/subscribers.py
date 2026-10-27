from app.domain.entities.subscriber import SubscriberProfile
from app.domain.repositories.subscribers import SubscriberRepository
from app.infrastructure.services.subscribers import SubscriberService


class SubscriberRepositoryAdapter(SubscriberRepository):
    def __init__(self, service: SubscriberService) -> None:
        self._service = service

    def get_profile(self, msisdn_a: str) -> SubscriberProfile | None:
        return self._service.get_profile(msisdn_a)
