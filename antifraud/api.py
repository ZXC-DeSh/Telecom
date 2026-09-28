import json
import logging
import os
from pathlib import Path
import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import Field

from .model import RiskModel
from .schemas import Approval, CallStart, CompletedCall, NumberQuery, PrivilegeRequest, Revocation
from .service import ScoringService
from .storage import Store


def create_app(store=None, model=None, keys=None):
    config = keys if keys is not None else {
        "operator": os.getenv("ANTIFRAUD_OPERATOR_KEY", ""),
        "admin": os.getenv("ANTIFRAUD_ADMIN_KEY", ""),
        "organizations": json.loads(os.getenv("ANTIFRAUD_ORG_KEYS_JSON", "{}")),
    }
    configured = [config.get("operator"), config.get("admin"), *config.get("organizations", {}).values()]
    active = [k for k in configured if k]
    if len(active) != len(set(active)):
        raise ValueError("Operator, admin and organization API keys must be distinct")
    if any(len(k) < 24 for k in active):
        raise ValueError("Use random API keys with at least 24 characters")
    if store is None:
        db_path = Path(os.getenv("ANTIFRAUD_DB", "runtime/antifraud.sqlite3"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        store = Store(db_path)
    if model is None:
        try:
            model = RiskModel.load(os.getenv("ANTIFRAUD_MODEL", "artifacts/model.json"))
        except (OSError, ValueError, KeyError, TypeError):
            logging.getLogger(__name__).exception("Model could not be loaded; fail-open mode")
    service = ScoringService(store, model)
    app = FastAPI(title="Telecom Antifraud", version="0.1.0",
                  description="Скоринг только по метаданным. Все решения рекомендательные. Автоблокировка отключена.")
    app.state.service = service

    def require_role(role):
        def dependency(x_api_key: Annotated[str | None, Header()] = None):
            expected = config.get(role)
            if not expected:
                raise HTTPException(503, "API key is not configured")
            if not x_api_key or not secrets.compare_digest(x_api_key, expected):
                raise HTTPException(401, "Invalid API key")
            return role
        return dependency

    operator = Depends(require_role("operator"))
    admin = Depends(require_role("admin"))

    def organization(x_api_key: Annotated[str | None, Header()] = None):
        if x_api_key:
            for org, expected in config.get("organizations", {}).items():
                if expected and secrets.compare_digest(x_api_key, expected):
                    return org
        raise HTTPException(401, "Invalid organization API key")

    @app.get("/health")
    def health():
        return {"status": "ok" if service.model else "degraded", "model_loaded": service.model is not None,
                "auto_block": False, "mode": "demo"}

    @app.post("/v1/calls/score", dependencies=[operator])
    def score_call(call: CallStart):
        return service.score_call(call)

    @app.post("/v1/numbers/score", dependencies=[operator])
    def score_number(query: NumberQuery):
        return service.score_number(query)

    @app.post("/v1/history", dependencies=[operator])
    def ingest(calls: Annotated[list[CompletedCall], Field(min_length=1, max_length=1000)]):
        try:
            return {"inserted": store.ingest(calls)}
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/v1/privileges/requests", status_code=201)
    def request_privilege(body: PrivilegeRequest, org=Depends(organization)):
        return store.request(org, body)

    @app.get("/v1/privileges/requests")
    def own_requests(org=Depends(organization)):
        return store.list_requests(org)

    @app.get("/v1/admin/privileges", dependencies=[admin])
    def requests():
        return store.list_requests()

    @app.post("/v1/admin/privileges/{request_id}/approve", dependencies=[admin])
    def approve(request_id: str, body: Approval):
        try:
            return store.approve(request_id, body)
        except KeyError as exc:
            raise HTTPException(404, "Request not found") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/v1/admin/privileges/{request_id}/revoke", dependencies=[admin])
    def revoke(request_id: str, body: Revocation):
        try:
            return store.revoke(request_id, body.reason)
        except KeyError as exc:
            raise HTTPException(404, "Request not found or already revoked") from exc

    @app.get("/v1/admin/audit", dependencies=[admin])
    def audit():
        return store.audit_rows()

    return app
