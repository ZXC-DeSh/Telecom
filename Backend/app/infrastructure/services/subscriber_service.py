from app.domain.entities.subscriber import SubscriberProfile
from app.domain.exceptions import FeatureUnavailable


class UnconfiguredSubscriberService:
    def get_profile(self, msisdn: str) -> SubscriberProfile | None:
        raise FeatureUnavailable("Subscriber query source is not configured")
