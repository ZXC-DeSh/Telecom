from app.application.exceptions import EntityNotFound
from app.domain.entities.subscriber import SubscriberProfile
from app.domain.repositories.subscribers import SubscriberRepository


class GetSubscriberProfile:
    def __init__(self, subscribers: SubscriberRepository):
        self._subscribers = subscribers

    def execute(self, msisdn: str) -> SubscriberProfile:
        profile = self._subscribers.get_profile(msisdn)
        if profile is None:
            raise EntityNotFound(f"Subscriber {msisdn} was not found")
        return profile
