from fastapi import APIRouter, Request

from app.api.schemas.model import ModelInfo
from app.api.schemas.response import ApiResponse

router = APIRouter(tags=["model"])


@router.get("/model/info", response_model=ApiResponse[ModelInfo])
def get_model_info(request: Request) -> ApiResponse[ModelInfo]:
    model = request.app.state.container.get_model_info.execute()
    return ApiResponse[ModelInfo](
        status_code=200,
        message="Информация о модели получена",
        data=ModelInfo.model_validate(model),
    )
