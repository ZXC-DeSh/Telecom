from app.domain.exceptions import AnalysisAlreadyRunning, FeatureUnavailable


class EntityNotFound(LookupError):
    pass


__all__ = ["AnalysisAlreadyRunning", "EntityNotFound", "FeatureUnavailable"]
