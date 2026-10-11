from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.schemas.health import DependencyHealth, HealthData
from app.api.schemas.response import ApiResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse[HealthData])
def health(request: Request) -> JSONResponse:
    dependencies = request.app.state.container.check_service_health.execute()
    status_code = 200 if dependencies.is_healthy else 503
    database = DependencyHealth(
        status="ok" if dependencies.database_available else "unavailable",
        message="Database is available" if dependencies.database_available else "Database unavailable",
    )
    model = DependencyHealth(
        status="ok" if dependencies.model_available else "unavailable",
        message="Prediction model is available" if dependencies.model_available else "Model unavailable",
    )
    response = ApiResponse[HealthData](
        status_code=status_code,
        message="Service healthy" if dependencies.is_healthy else "Service degraded",
        data=HealthData(
            status="ok" if dependencies.is_healthy else "degraded",
            database=database,
            model=model,
        ),
    )
    return JSONResponse(status_code=status_code, content=response.model_dump())
