class FeatureUnavailable(RuntimeError):
    """Raised when an optional domain capability has no configured adapter."""


class AnalysisAlreadyRunning(RuntimeError):
    """Raised when another analysis job is already running."""
