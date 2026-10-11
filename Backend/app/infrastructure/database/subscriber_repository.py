from app.application.exceptions import FeatureUnavailable
from app.domain.entities.subscriber import SubscriberProfile


class UnconfiguredSubscriberRepository:
    def get_profile(self, msisdn: str) -> SubscriberProfile | None:
        raise FeatureUnavailable("Subscriber query source is not configured")
