from fastapi import APIRouter

from .routers.analysis import router as analysis_router
from .routers.calls import router as calls_router
from .routers.dashboard import router as dashboard_router
from .routers.fraud_alerts import router as fraud_alerts_router
from .routers.health import router as health_router
from .routers.model import router as model_router
from .routers.predictions import router as predictions_router
from .routers.subscribers import router as subscribers_router


def build_router(prefix: str) -> APIRouter:
    router = APIRouter()
    router.include_router(health_router, prefix=prefix)
    router.include_router(analysis_router, prefix=prefix)
    router.include_router(calls_router, prefix=prefix)
    router.include_router(dashboard_router, prefix=prefix)
    router.include_router(fraud_alerts_router, prefix=prefix)
    router.include_router(model_router, prefix=prefix)
    router.include_router(predictions_router, prefix=prefix)
    router.include_router(subscribers_router, prefix=prefix)
    return router
