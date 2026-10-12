import logging
from datetime import datetime, time, timedelta
from uuid import UUID

from app.application.use_cases.predict_fraud import PredictFraud
from app.domain.entities.analysis_job import AnalysisMetrics
from app.domain.entities.prediction import Prediction
from app.domain.entities.search import CallSearchCriteria
from app.domain.repositories.analysis_jobs import AnalysisJobRepository
from app.domain.repositories.calls import CallRepository
from app.domain.value_objects import AnalysisStatus, RiskLevel

logger = logging.getLogger(__name__)


class ProcessAnalysis:
    """Scores calls for an accepted analysis job and persists their assessments."""

    def __init__(
        self,
        jobs: AnalysisJobRepository,
        calls: CallRepository,
        predictor: PredictFraud,
    ) -> None:
        self._jobs = jobs
        self._calls = calls
        self._predictor = predictor

    def execute(self, job_id: UUID) -> None:
        job = self._jobs.get_by_id(job_id)
        if job is None:
            logger.error("analysis job %s disappeared before processing", job_id)
            return
        if job.status != AnalysisStatus.QUEUED:
            logger.warning(
                "analysis job %s was not queued when processing started (status=%s)",
                job_id,
                job.status,
            )
            return
        force_recalculate = job.force_recalculate

        metrics = _empty_metrics()
        progress = 0.0
        try:
            self._jobs.mark_running(job_id)
            date_from = datetime.combine(job.date_from.date(), time.min)
            date_to_exclusive = datetime.combine(
                job.date_to.date() + timedelta(days=1), time.min
            )
            criteria = CallSearchCriteria(
                page=1,
                page_size=100,
                date_from=date_from,
                date_to_exclusive=date_to_exclusive,
            )
            first_page = self._calls.list(criteria)
            total_calls = first_page.total
            metrics = _empty_metrics(total_calls=total_calls)
            page_count = first_page.pages

            for page_number in range(1, page_count + 1):
                page = (
                    first_page
                    if page_number == 1
                    else self._calls.list(
                        CallSearchCriteria(
                            page=page_number,
                            page_size=100,
                            date_from=date_from,
                            date_to_exclusive=date_to_exclusive,
                        )
                    )
                )
                for call in page.items:
                    if call.assessment is not None and not force_recalculate:
                        metrics = _include_prediction(metrics, call.assessment)
                        continue
                    prediction = self._predictor.execute(call=call)
                    metrics = _include_prediction(metrics, prediction)
                progress = min(100.0, page_number * 100.0 / max(page_count, 1))
                self._jobs.update_progress(job_id, progress, metrics)

            self._jobs.complete(job_id, metrics)
        except Exception as exc:
            logger.exception("analysis job %s failed", job_id)
            self._jobs.fail(
                job_id,
                str(exc) or type(exc).__name__,
                metrics=metrics,
                progress_percent=progress,
            )


def _empty_metrics(total_calls: int = 0) -> AnalysisMetrics:
    return AnalysisMetrics(
        total_calls=total_calls,
        processed_calls=0,
        fraud_calls=0,
        low_risk_calls=0,
        medium_risk_calls=0,
        high_risk_calls=0,
        critical_risk_calls=0,
    )


def _include_prediction(
    metrics: AnalysisMetrics, prediction: Prediction
) -> AnalysisMetrics:
    counts = {
        RiskLevel.LOW: metrics.low_risk_calls,
        RiskLevel.MEDIUM: metrics.medium_risk_calls,
        RiskLevel.HIGH: metrics.high_risk_calls,
        RiskLevel.CRITICAL: metrics.critical_risk_calls,
    }
    counts[prediction.risk_level] += 1
    return AnalysisMetrics(
        total_calls=metrics.total_calls,
        processed_calls=metrics.processed_calls + 1,
        fraud_calls=metrics.fraud_calls + int(prediction.is_fraud),
        low_risk_calls=counts[RiskLevel.LOW],
        medium_risk_calls=counts[RiskLevel.MEDIUM],
        high_risk_calls=counts[RiskLevel.HIGH],
        critical_risk_calls=counts[RiskLevel.CRITICAL],
    )
