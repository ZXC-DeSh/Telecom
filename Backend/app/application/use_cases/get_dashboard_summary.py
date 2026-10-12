from app.domain.entities.dashboard import DashboardSummary
from app.domain.repositories.dashboard import DashboardRepository


class GetDashboardSummary:
    def __init__(self, dashboard: DashboardRepository):
        self._dashboard = dashboard

    def execute(self) -> DashboardSummary:
        return self._dashboard.get_summary()
