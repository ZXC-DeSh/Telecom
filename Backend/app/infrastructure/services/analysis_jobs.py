import json
from dataclasses import asdict
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg2.extras import Json

from app.domain.entities.analysis_job import AnalysisJob, AnalysisMetrics
from app.domain.exceptions import AnalysisAlreadyRunning
from app.domain.value_objects import AnalysisStatus
from app.infrastructure.database.connection import Database
from app.infrastructure.database.query import CurrentTimestamp, Filter, Sort


class AnalysisJobService:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(
        self, date_from: datetime, date_to: datetime, force_recalculate: bool
    ) -> AnalysisJob:
        running_job = self._database.select_one(
            "public.analysis_jobs",
            ("job_id",),
            filters=(Filter("status", "=", AnalysisStatus.RUNNING.value),),
        )
        if running_job is not None:
            raise AnalysisAlreadyRunning("Анализ уже выполняется")

        job_id = uuid4()
        row = self._database.insert(
            "public.analysis_jobs",
            {
                "job_id": job_id,
                "status": AnalysisStatus.QUEUED.value,
                "date_from": date_from,
                "date_to": date_to,
                "force_recalculate": force_recalculate,
            },
            returning=("created_at",),
        )
        if row is None:
            raise RuntimeError("создание задания анализа не вернуло время создания")
        created_at = row[0]
        return AnalysisJob(
            job_id=job_id,
            status=AnalysisStatus.QUEUED,
            date_from=date_from,
            date_to=date_to,
            created_at=created_at,
            force_recalculate=force_recalculate,
        )

    def get_by_id(self, job_id: UUID) -> AnalysisJob | None:
        row = self._database.select_one(
            "public.analysis_jobs",
            (
                "job_id",
                "status",
                "date_from",
                "date_to",
                "created_at",
                "progress_percent",
                "started_at",
                "finished_at",
                "metrics",
                "error",
                "force_recalculate",
            ),
            filters=(Filter("job_id", "=", job_id),),
        )
        if row is None:
            return None

        return _analysis_job_from_row(row)

    def get_current(self) -> tuple[tuple[AnalysisJob, ...], AnalysisJob | None]:
        fields = (
            "job_id",
            "status",
            "date_from",
            "date_to",
            "created_at",
            "progress_percent",
            "started_at",
            "finished_at",
            "metrics",
            "error",
            "force_recalculate",
        )
        active_rows = self._database.select_all(
            "public.analysis_jobs",
            fields,
            filters=(
                Filter(
                    "status",
                    "IN",
                    (AnalysisStatus.QUEUED.value, AnalysisStatus.RUNNING.value),
                ),
            ),
            order_by=(Sort("created_at", "ASC"),),
        )
        latest_rows = self._database.select_all(
            "public.analysis_jobs",
            fields,
            order_by=(Sort("created_at", "DESC"), Sort("job_id", "DESC")),
            limit=1,
        )
        active_jobs = tuple(_analysis_job_from_row(row) for row in active_rows)
        latest_job = _analysis_job_from_row(latest_rows[0]) if latest_rows else None
        return active_jobs, latest_job

    def mark_running(self, job_id: UUID) -> None:
        self._update(
            {
                "status": AnalysisStatus.RUNNING.value,
                "started_at": CurrentTimestamp(),
            },
            job_id,
        )

    def update_progress(
        self, job_id: UUID, progress_percent: float, metrics: AnalysisMetrics
    ) -> None:
        self._update(
            {"progress_percent": progress_percent, "metrics": Json(asdict(metrics))},
            job_id,
        )

    def complete(self, job_id: UUID, metrics: AnalysisMetrics) -> None:
        self._update(
            {
                "status": AnalysisStatus.COMPLETED.value,
                "progress_percent": 100,
                "finished_at": CurrentTimestamp(),
                "metrics": Json(asdict(metrics)),
                "error": None,
            },
            job_id,
        )

    def fail(
        self,
        job_id: UUID,
        error: str,
        metrics: AnalysisMetrics | None = None,
        progress_percent: float | None = None,
    ) -> None:
        values: dict[str, object] = {
            "status": AnalysisStatus.FAILED.value,
            "finished_at": CurrentTimestamp(),
            "error": error[:2000],
        }
        if metrics is not None:
            values["metrics"] = Json(asdict(metrics))
        if progress_percent is not None:
            values["progress_percent"] = progress_percent
        self._update(values, job_id)

    def fail_unfinished(self, error: str) -> None:
        self._database.update(
            "public.analysis_jobs",
            {
                "status": AnalysisStatus.FAILED.value,
                "finished_at": CurrentTimestamp(),
                "error": error[:2000],
            },
            filters=(
                Filter(
                    "status",
                    "IN",
                    (AnalysisStatus.QUEUED.value, AnalysisStatus.RUNNING.value),
                ),
            ),
        )

    def _update(self, values: dict[str, object], job_id: UUID) -> None:
        self._database.update(
            "public.analysis_jobs",
            values,
            filters=(Filter("job_id", "=", job_id),),
        )


def _analysis_job_from_row(row: tuple[Any, ...]) -> AnalysisJob:
    raw_metrics = row[8]
    if isinstance(raw_metrics, str):
        raw_metrics = json.loads(raw_metrics)
    metrics = AnalysisMetrics(**raw_metrics) if raw_metrics is not None else None
    return AnalysisJob(
        job_id=row[0],
        status=row[1],
        date_from=row[2],
        date_to=row[3],
        created_at=row[4],
        progress_percent=row[5],
        started_at=row[6],
        finished_at=row[7],
        metrics=metrics,
        error=row[9],
        force_recalculate=row[10],
    )
