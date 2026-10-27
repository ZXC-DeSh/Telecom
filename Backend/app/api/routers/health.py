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
        message="База данных доступна"
        if dependencies.database_available
        else "База данных недоступна",
    )
    model = DependencyHealth(
        status="ok" if dependencies.model_available else "unavailable",
        message="Модель прогнозирования доступна"
        if dependencies.model_available
        else "Модель прогнозирования недоступна",
    )
    response = ApiResponse[HealthData](
        status_code=status_code,
        message="Сервис работает штатно"
        if dependencies.is_healthy
        else "Работа сервиса нарушена",
        data=HealthData(
            status="ok" if dependencies.is_healthy else "degraded",
            database=database,
            model=model,
        ),
    )
    return JSONResponse(status_code=status_code, content=response.model_dump())
