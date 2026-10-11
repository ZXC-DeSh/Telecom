from datetime import datetime
from uuid import UUID

from app.application.exceptions import FeatureUnavailable
from app.domain.entities.analysis_job import AnalysisJob


class UnconfiguredAnalysisJobRepository:
    def create(
        self, date_from: datetime, date_to: datetime, force_recalculate: bool
    ) -> AnalysisJob:
        raise FeatureUnavailable("Analysis job storage is not configured")

    def get_by_id(self, job_id: UUID) -> AnalysisJob | None:
        raise FeatureUnavailable("Analysis job storage is not configured")
