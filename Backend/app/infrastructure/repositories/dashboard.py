from app.domain.entities.dashboard import DashboardSummary
from app.domain.repositories.dashboard import DashboardRepository
from app.infrastructure.services.dashboard import DashboardService


class DashboardRepositoryAdapter(DashboardRepository):
    def __init__(self, service: DashboardService) -> None:
        self._service = service

    def get_summary(self) -> DashboardSummary:
        return self._service.get_summary()

    def refresh_summary_cache(self) -> None:
        self._service.refresh_summary_cache()

    @property
    def refresh_status(self) -> str:
        return self._service.refresh_status
