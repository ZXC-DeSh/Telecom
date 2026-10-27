from datetime import datetime
from uuid import UUID

from app.application.exceptions import EntityNotFound
from app.domain.entities.analysis_job import AnalysisJob
from app.domain.repositories.analysis_jobs import AnalysisJobRepository


class RunAnalysis:
    def __init__(self, jobs: AnalysisJobRepository):
        self._jobs = jobs

    def execute(
        self, date_from: datetime, date_to: datetime, force_recalculate: bool = False
    ) -> AnalysisJob:
        if date_from.utcoffset() is not None or date_to.utcoffset() is not None:
            raise ValueError("даты анализа не должны содержать часовой пояс")
        if date_to < date_from:
            raise ValueError("date_to должен быть не раньше date_from")
        return self._jobs.create(date_from, date_to, force_recalculate)


class GetAnalysisStatus:
    def __init__(self, jobs: AnalysisJobRepository):
        self._jobs = jobs

    def execute(self, job_id: UUID) -> AnalysisJob:
        job = self._jobs.get_by_id(job_id)
        if job is None:
            raise EntityNotFound(
                f"Задание анализа с идентификатором {job_id} не найдено"
            )
        return job


class GetCurrentAnalysis:
    def __init__(self, jobs: AnalysisJobRepository):
        self._jobs = jobs

    def execute(self) -> tuple[tuple[AnalysisJob, ...], AnalysisJob | None]:
        return self._jobs.get_current()


class FailUnfinishedAnalysisJobs:
    def __init__(self, jobs: AnalysisJobRepository):
        self._jobs = jobs

    def execute(self, error: str) -> None:
        self._jobs.fail_unfinished(error)
