from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Request

from app.api.schemas.analysis import (
    AnalysisJobAccepted,
    AnalysisJobStatus,
    AnalysisRunRequest,
    CurrentAnalysis,
)
from app.api.schemas.response import ApiResponse
from app.domain.value_objects import AnalysisStatus

router = APIRouter(tags=["analysis"])


@router.get("/analysis/current", response_model=ApiResponse[CurrentAnalysis])
def get_current_analysis(request: Request) -> ApiResponse[CurrentAnalysis]:
    jobs, latest_job = request.app.state.container.get_current_analysis.execute()
    active_job = next(
        (job for job in jobs if job.status == AnalysisStatus.RUNNING), None
    )
    queued_jobs = tuple(job for job in jobs if job.status == AnalysisStatus.QUEUED)
    last_failed_job = None
    last_successful_job = None
    if latest_job is not None:
        if latest_job.status == AnalysisStatus.FAILED:
            last_failed_job = AnalysisJobStatus.model_validate(latest_job)
        elif latest_job.status == AnalysisStatus.COMPLETED:
            last_successful_job = AnalysisJobStatus.model_validate(latest_job)
    data = CurrentAnalysis(
        active_job=AnalysisJobStatus.model_validate(active_job)
        if active_job is not None
        else None,
        queued_jobs=[AnalysisJobStatus.model_validate(job) for job in queued_jobs]
        if queued_jobs
        else None,
        last_failed_job=last_failed_job,
        last_successful_job=last_successful_job,
    )
    return ApiResponse[CurrentAnalysis](
        status_code=200,
        message="Текущие задания анализа получены",
        data=data,
    )


@router.post(
    "/analysis/run",
    response_model=ApiResponse[AnalysisJobAccepted],
    status_code=202,
)
def run_analysis(
    payload: AnalysisRunRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> ApiResponse[AnalysisJobAccepted]:
    job = request.app.state.container.run_analysis.execute(
        date_from=payload.date_from,
        date_to=payload.date_to,
        force_recalculate=payload.force_recalculate,
    )
    background_tasks.add_task(
        request.app.state.container.process_analysis.execute,
        job.job_id,
    )
    return ApiResponse[AnalysisJobAccepted](
        status_code=202,
        message="Задание анализа принято",
        data=AnalysisJobAccepted.model_validate(job),
    )


@router.get("/analysis/{job_id}", response_model=ApiResponse[AnalysisJobStatus])
def get_analysis_status(
    job_id: UUID, request: Request
) -> ApiResponse[AnalysisJobStatus]:
    job = request.app.state.container.get_analysis_status.execute(job_id)
    return ApiResponse[AnalysisJobStatus](
        status_code=200,
        message="Статус анализа получен",
        data=AnalysisJobStatus.model_validate(job),
    )
