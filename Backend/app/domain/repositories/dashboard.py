from typing import Protocol

from app.domain.entities.dashboard import DashboardSummary


class DashboardRepository(Protocol):
    def get_summary(self) -> DashboardSummary: ...

    def refresh_summary_cache(self) -> None: ...

    @property
    def refresh_status(self) -> str: ...
