from app.application.exceptions import FeatureUnavailable
from app.domain.entities.dashboard import DashboardSummary


class UnconfiguredDashboardRepository:
    def get_summary(self) -> DashboardSummary:
        raise FeatureUnavailable("Dashboard query source is not configured")
