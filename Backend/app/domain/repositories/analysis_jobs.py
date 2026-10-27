from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.entities.analysis_job import AnalysisJob, AnalysisMetrics


class AnalysisJobRepository(Protocol):
    def create(
        self, date_from: datetime, date_to: datetime, force_recalculate: bool
    ) -> AnalysisJob: ...

    def get_by_id(self, job_id: UUID) -> AnalysisJob | None: ...

    def get_current(self) -> tuple[tuple[AnalysisJob, ...], AnalysisJob | None]: ...

    def fail_unfinished(self, error: str) -> None: ...

    def mark_running(self, job_id: UUID) -> None: ...

    def update_progress(
        self, job_id: UUID, progress_percent: float, metrics: AnalysisMetrics
    ) -> None: ...

    def complete(self, job_id: UUID, metrics: AnalysisMetrics) -> None: ...

    def fail(
        self,
        job_id: UUID,
        error: str,
        metrics: AnalysisMetrics | None = None,
        progress_percent: float | None = None,
    ) -> None: ...
