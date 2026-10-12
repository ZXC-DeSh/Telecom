from app.domain.exceptions import FeatureUnavailable


class EntityNotFound(LookupError):
    pass


__all__ = ["EntityNotFound", "FeatureUnavailable"]
