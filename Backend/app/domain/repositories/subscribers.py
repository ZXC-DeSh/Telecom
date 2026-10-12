from typing import Protocol

from app.domain.entities.subscriber import SubscriberProfile


class SubscriberRepository(Protocol):
    def get_profile(self, msisdn: str) -> SubscriberProfile | None: ...
