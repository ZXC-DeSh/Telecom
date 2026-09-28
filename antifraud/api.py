"""Локальное демо: визуальный интерфейс и API без ключей и учётных записей."""
import json
import logging
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from .catalog import DemoCatalog, add_demo_privilege
from .model import RiskModel
from .schemas import CallStart, CompletedCall, NumberQuery, RegistryNumber
from .service import ScoringService
from .storage import Store

PROJECT_DIR = Path(__file__).resolve().parents[1]


def create_app(store=None, model=None):
    if store is None:
        db_path = PROJECT_DIR / "runtime" / "antifraud.sqlite3"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        store = Store(db_path)
    if model is None:
        try:
            model = RiskModel.load(PROJECT_DIR / "artifacts" / "model.json")
        except (OSError, ValueError, KeyError, TypeError):
            logging.getLogger(__name__).exception("Модель недоступна, вызовы будут пропускаться")
    service = ScoringService(store, model)
    catalog = DemoCatalog(store)
    app = FastAPI(title="Телеком Антифрод", version="0.2.0",
                  description="Локальная демонстрация без авторизации. Оценка по метаданным, без блокировки звонков.")
    app.state.service = service
    app.mount("/static", StaticFiles(directory=PROJECT_DIR / "static"), name="static")

    @app.get("/", include_in_schema=False)
    def interface():
        return FileResponse(PROJECT_DIR / "static" / "index.html")

    @app.get("/health", summary="Состояние модели")
    def health():
        return {"status": "ok" if service.model else "degraded", "model_loaded": service.model is not None,
                "auto_block": False, "mode": "demo"}

    @app.post("/v1/calls/score", summary="Оценить вызов")
    def score_call(call: CallStart):
        return service.score_call(call)

    @app.post("/v1/numbers/score", summary="Оценить номер")
    def score_number(query: NumberQuery):
        return service.score_number(query)

    @app.post("/v1/history", summary="Добавить историю вызовов")
    def ingest(calls: Annotated[list[CompletedCall], Field(min_length=1, max_length=1000)]):
        try:
            return {"inserted": store.ingest(calls)}
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/v1/demo/scenarios", summary="Готовые примеры для интерфейса")
    def scenarios():
        return catalog.load()

    @app.get("/v1/demo/metrics", summary="Результаты на синтетических данных")
    def metrics():
        report = json.loads((PROJECT_DIR / "artifacts" / "metrics.json").read_text(encoding="utf-8"))
        manifest = json.loads((PROJECT_DIR / "data" / "manifest.json").read_text(encoding="utf-8"))
        return {"test": report["splits"]["test"], "queries": manifest["queries"],
                "calls": manifest["calls"], "synthetic_only": True}

    @app.get("/v1/privileges", summary="Привилегированные номера")
    def registry():
        return store.list_requests()

    @app.post("/v1/privileges", status_code=201, summary="Добавить номер в демореестр")
    def add_privilege(body: RegistryNumber):
        try:
            return add_demo_privilege(store, body.number, body.organization)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.delete("/v1/privileges/{entry_id}", summary="Отозвать привилегию")
    def revoke(entry_id: str):
        try:
            return store.revoke(entry_id, "Отозвано в демонстрационном интерфейсе")
        except KeyError as exc:
            raise HTTPException(404, "Запись не найдена или уже отозвана") from exc

    return app
