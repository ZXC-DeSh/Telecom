import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.api.router import build_router
from app.container import Container
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.api.schemas.response import ApiResponse
from app.application.exceptions import EntityNotFound, FeatureUnavailable

logger = logging.getLogger(__name__)


def _error(status: int, message: str, data: object = None) -> JSONResponse:
    body = ApiResponse[object](status_code=status, message=message, data=data)
    return JSONResponse(status_code=status, content=jsonable_encoder(body))


def create_application(container: Container) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        yield
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
        messages = {404: "Not found", 405: "Method not allowed"}
        return _error(exc.status_code, messages.get(exc.status_code, str(exc.detail)))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error(
            400, "Invalid request", {"errors": jsonable_encoder(exc.errors())}
        )

    @app.exception_handler(EntityNotFound)
    async def entity_not_found(_: Request, exc: EntityNotFound) -> JSONResponse:
        return _error(404, str(exc))

    @app.exception_handler(FeatureUnavailable)
    async def feature_unavailable(_: Request, exc: FeatureUnavailable) -> JSONResponse:
        return _error(501, str(exc))

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled application error: %s",
            exc,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return _error(500, "Internal server error")

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
