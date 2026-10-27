import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.api.router import build_router
from app.api.schemas.response import ApiResponse
from app.application.exceptions import (
    AnalysisAlreadyRunning,
    EntityNotFound,
    FeatureUnavailable,
)
from app.container import Container
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)

_VALIDATION_MESSAGES = {
    "missing": "Поле обязательно для заполнения",
    "string_type": "Ожидалось текстовое значение",
    "string_too_short": "Текст короче допустимого минимума",
    "string_too_long": "Текст длиннее допустимого максимума",
    "int_type": "Ожидалось целое число",
    "int_parsing": "Не удалось преобразовать значение в целое число",
    "int_from_float": "Ожидалось целое число",
    "float_type": "Ожидалось число",
    "float_parsing": "Не удалось преобразовать значение в число",
    "bool_type": "Ожидалось логическое значение",
    "bool_parsing": "Не удалось преобразовать значение в логическое",
    "uuid_type": "Ожидался UUID",
    "uuid_parsing": "Некорректный UUID",
    "datetime_type": "Ожидались дата и время",
    "datetime_parsing": "Некорректный формат даты и времени",
    "date_type": "Ожидалась дата",
    "date_parsing": "Некорректный формат даты",
    "enum": "Недопустимое значение",
    "literal_error": "Недопустимое значение",
    "greater_than": "Значение меньше допустимого",
    "greater_than_equal": "Значение меньше допустимого минимума",
    "less_than": "Значение превышает допустимый максимум",
    "less_than_equal": "Значение превышает допустимый максимум",
    "finite_number": "Ожидалось конечное число",
    "extra_forbidden": "Дополнительное поле не разрешено",
    "list_type": "Ожидался список",
    "tuple_type": "Ожидался кортеж",
    "dict_type": "Ожидался объект",
    "json_invalid": "Некорректный JSON",
    "multiple_of": "Значение не соответствует допустимому шагу",
    "decimal_parsing": "Некорректное числовое значение",
}


def _error(status: int, message: str, data: object = None) -> JSONResponse:
    body = ApiResponse[object](status_code=status, message=message, data=data)
    return JSONResponse(status_code=status, content=jsonable_encoder(body))


def create_application(container: Container) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        try:
            yield
        finally:
            try:
                container.fail_unfinished_analysis_jobs.execute(
                    "Аварийное завершение сервера"
                )
            finally:
                container.close()

    app = FastAPI(
        title=container.settings.app_name,
        version=container.settings.api_prefix.rsplit("/", 1)[-1],
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.container = container
    app.include_router(build_router(container.settings.api_prefix))

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        messages = {404: "Не найдено", 405: "Метод не поддерживается"}
        return _error(exc.status_code, messages.get(exc.status_code, str(exc.detail)))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = jsonable_encoder(exc.errors())
        for error in errors:
            message = error.get("msg", "")
            if error.get("type") == "value_error" and message.startswith(
                "Value error, "
            ):
                error["msg"] = message.removeprefix("Value error, ")
            elif not any("\u0400" <= character <= "\u04ff" for character in message):
                error["msg"] = _VALIDATION_MESSAGES.get(
                    error.get("type"), "Недопустимое значение"
                )
        return _error(400, "Некорректный запрос", {"errors": errors})

    @app.exception_handler(EntityNotFound)
    async def entity_not_found(_: Request, exc: EntityNotFound) -> JSONResponse:
        return _error(404, str(exc))

    @app.exception_handler(FeatureUnavailable)
    async def feature_unavailable(_: Request, exc: FeatureUnavailable) -> JSONResponse:
        return _error(501, str(exc))

    @app.exception_handler(AnalysisAlreadyRunning)
    async def analysis_already_running(
        _: Request, exc: AnalysisAlreadyRunning
    ) -> JSONResponse:
        return _error(409, str(exc))

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled application error: %s",
            exc,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return _error(500, "Внутренняя ошибка сервера")

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    if container.settings.allowed_origins:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=container.settings.allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )
    return app


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    return create_application(Container.build(settings))
