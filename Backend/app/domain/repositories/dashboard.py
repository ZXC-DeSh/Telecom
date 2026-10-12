from typing import Protocol

from app.domain.entities.dashboard import DashboardSummary


class DashboardRepository(Protocol):
    def get_summary(self) -> DashboardSummary: ...
