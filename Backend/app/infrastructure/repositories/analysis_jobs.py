from datetime import datetime
from uuid import UUID

from app.domain.entities.analysis_job import AnalysisJob, AnalysisMetrics
from app.domain.repositories.analysis_jobs import AnalysisJobRepository
from app.infrastructure.services.analysis_job_service import PostgresAnalysisJobService


class PostgresAnalysisJobRepository(AnalysisJobRepository):
    def __init__(self, service: PostgresAnalysisJobService) -> None:
        self._service = service

    def create(
        self, date_from: datetime, date_to: datetime, force_recalculate: bool
    ) -> AnalysisJob:
        return self._service.create(date_from, date_to, force_recalculate)

    def get_by_id(self, job_id: UUID) -> AnalysisJob | None:
        return self._service.get_by_id(job_id)

    def mark_running(self, job_id: UUID) -> None:
        self._service.mark_running(job_id)

    def update_progress(
        self, job_id: UUID, progress_percent: float, metrics: AnalysisMetrics
    ) -> None:
        self._service.update_progress(job_id, progress_percent, metrics)

    def complete(self, job_id: UUID, metrics: AnalysisMetrics) -> None:
        self._service.complete(job_id, metrics)

    def fail(
        self,
        job_id: UUID,
        error: str,
        metrics: AnalysisMetrics | None = None,
        progress_percent: float | None = None,
    ) -> None:
        self._service.fail(job_id, error, metrics, progress_percent)
