import json
from typing import Any

from app.domain.entities.fraud_alert import FraudAlert, FraudAlertPage
from app.domain.entities.page import Page
from app.domain.entities.prediction_reason import PredictionReason
from app.domain.entities.search import FraudAlertSearchCriteria
from app.infrastructure.database.connection import Database
from app.infrastructure.database.query import Filter, FilterGroup, Sort


class FraudAlertService:
    def __init__(self, database: Database) -> None:
        self._database = database

    def list(self, criteria: FraudAlertSearchCriteria) -> FraudAlertPage:
        filters: list[Filter | FilterGroup] = []
        if criteria.risk_level is not None:
            filters.append(Filter("fa.risk_level", "=", criteria.risk_level.value))
        if criteria.fraud_scenario is not None:
            filters.append(
                Filter("fa.fraud_scenario", "=", criteria.fraud_scenario.value)
            )
        if criteria.msisdn is not None:
            filters.append(
                FilterGroup(
                    (
                        Filter("fa.msisdn_a", "=", criteria.msisdn),
                        Filter("fa.msisdn_b", "=", criteria.msisdn),
                        Filter("fa.msisdn_c", "=", criteria.msisdn),
                    )
                )
            )
        if criteria.date_from is not None:
            filters.append(Filter("fa.call_time", ">=", criteria.date_from))
        if criteria.date_to is not None:
            filters.append(Filter("fa.call_time", "<=", criteria.date_to))
        offset = (criteria.page - 1) * criteria.page_size
        total = self._database.count(
            "public.fraud_alerts_view", alias="fa", filters=filters
        )
        rows = self._database.select_all(
            "public.fraud_alerts_view",
            (
                "fa.alert_id",
                "fa.call_id",
                "fa.call_time",
                "fa.msisdn_a",
                "fa.msisdn_b",
                "fa.duration_seconds",
                "fa.risk_score",
                "fa.risk_level",
                "fa.fraud_scenario",
                "fa.reasons",
                "fa.recommendation",
                "fa.auto_blocked",
            ),
            alias="fa",
            filters=filters,
            order_by=(Sort("fa.call_time", "DESC"), Sort("fa.call_id", "DESC")),
            limit=criteria.page_size,
            offset=offset,
        )
        items = tuple(_alert_from_row(row) for row in rows)
        return Page(
            items=items,
            page=criteria.page,
            page_size=criteria.page_size,
            total=total,
        )


def _alert_from_row(row: tuple[Any, ...]) -> FraudAlert:
    raw_reasons = row[9]
    if isinstance(raw_reasons, str):
        raw_reasons = json.loads(raw_reasons)
    reasons = tuple(PredictionReason(**reason) for reason in (raw_reasons or []))
    return FraudAlert(
        alert_id=row[0],
        call_id=row[1],
        call_time=row[2],
        msisdn_a=row[3],
        msisdn_b=row[4],
        duration_seconds=row[5],
        risk_score=row[6],
        risk_level=row[7],
        fraud_scenario=row[8],
        reasons=reasons,
        recommendation=row[10],
        auto_blocked=row[11],
    )
