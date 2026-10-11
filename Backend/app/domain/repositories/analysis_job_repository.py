from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.entities.analysis_job import AnalysisJob


class AnalysisJobRepository(Protocol):
    def create(
        self, date_from: datetime, date_to: datetime, force_recalculate: bool
    ) -> AnalysisJob: ...

    def get_by_id(self, job_id: UUID) -> AnalysisJob | None: ...
