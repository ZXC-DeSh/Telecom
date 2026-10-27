from fastapi import APIRouter, Request

from app.api.schemas.dashboard import (
    DashboardRefreshStatus,
    DashboardSummary as DashboardSummarySchema,
)
from app.api.schemas.response import ApiResponse

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary", response_model=ApiResponse[DashboardSummarySchema])
def get_dashboard_summary(request: Request) -> ApiResponse[DashboardSummarySchema]:
    summary = request.app.state.container.get_dashboard_summary.execute()
    return ApiResponse[DashboardSummarySchema](
        status_code=200,
        message="Сводка панели получена",
        data=DashboardSummarySchema.model_validate(summary),
    )


@router.get(
    "/dashboard/refresh-status",
    response_model=ApiResponse[DashboardRefreshStatus],
)
def get_dashboard_refresh_status(
    request: Request,
) -> ApiResponse[DashboardRefreshStatus]:
    status = request.app.state.container.dashboard_repository.refresh_status
    return ApiResponse[DashboardRefreshStatus](
        status_code=200,
        message="Статус обновления статистики получен",
        data=DashboardRefreshStatus(status=status),
    )
