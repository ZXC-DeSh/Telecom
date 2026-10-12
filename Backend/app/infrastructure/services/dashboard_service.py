from app.domain.entities.dashboard import DashboardSummary
from app.domain.exceptions import FeatureUnavailable


class UnconfiguredDashboardService:
    def get_summary(self) -> DashboardSummary:
        raise FeatureUnavailable("Dashboard query source is not configured")
