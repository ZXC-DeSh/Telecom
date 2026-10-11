from uuid import UUID

from fastapi import APIRouter, Request

from app.api.schemas.analysis import (
    AnalysisJobAccepted,
    AnalysisJobStatus,
    AnalysisRunRequest,
)
from app.api.schemas.response import ApiResponse

router = APIRouter(tags=["analysis"])


@router.post(
    "/analysis/run",
    response_model=ApiResponse[AnalysisJobAccepted],
    status_code=202,
)
def run_analysis(
    payload: AnalysisRunRequest,
    request: Request,
) -> ApiResponse[AnalysisJobAccepted]:
    job = request.app.state.container.run_analysis.execute(
        date_from=payload.date_from,
        date_to=payload.date_to,
        force_recalculate=payload.force_recalculate,
    )
    return ApiResponse[AnalysisJobAccepted](
        status_code=202,
        message="Analysis job accepted",
        data=AnalysisJobAccepted.model_validate(job),
    )


@router.get("/analysis/{job_id}", response_model=ApiResponse[AnalysisJobStatus])
def get_analysis_status(job_id: UUID, request: Request) -> ApiResponse[AnalysisJobStatus]:
    job = request.app.state.container.get_analysis_status.execute(job_id)
    return ApiResponse[AnalysisJobStatus](
        status_code=200,
        message="Analysis status retrieved",
        data=AnalysisJobStatus.model_validate(job),
    )
