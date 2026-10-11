from datetime import datetime
from uuid import UUID

from app.application.exceptions import EntityNotFound
from app.domain.entities.analysis_job import AnalysisJob
from app.domain.repositories.analysis_job_repository import AnalysisJobRepository


class RunAnalysis:
    def __init__(self, jobs: AnalysisJobRepository):
        self._jobs = jobs

    def execute(
        self, date_from: datetime, date_to: datetime, force_recalculate: bool = False
    ) -> AnalysisJob:
        if date_from.utcoffset() is not None or date_to.utcoffset() is not None:
            raise ValueError("analysis dates must be timezone-naive")
        if date_to < date_from:
            raise ValueError("date_to must be greater than or equal to date_from")
        return self._jobs.create(date_from, date_to, force_recalculate)


class GetAnalysisStatus:
    def __init__(self, jobs: AnalysisJobRepository):
        self._jobs = jobs

    def execute(self, job_id: UUID) -> AnalysisJob:
        job = self._jobs.get_by_id(job_id)
        if job is None:
            raise EntityNotFound(f"Analysis job {job_id} was not found")
        return job
