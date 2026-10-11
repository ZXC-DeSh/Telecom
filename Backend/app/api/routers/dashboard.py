from fastapi import APIRouter, Request

from app.api.schemas.dashboard import DashboardSummary as DashboardSummarySchema
from app.api.schemas.response import ApiResponse

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary", response_model=ApiResponse[DashboardSummarySchema])
def get_dashboard_summary(request: Request) -> ApiResponse[DashboardSummarySchema]:
    summary = request.app.state.container.get_dashboard_summary.execute()
    return ApiResponse[DashboardSummarySchema](
        status_code=200,
        message="Dashboard summary retrieved",
        data=DashboardSummarySchema.model_validate(summary),
    )
