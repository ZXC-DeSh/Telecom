import json
from uuid import UUID

from app.domain.entities.call import Call
from app.domain.entities.page import Page
from app.domain.entities.prediction import Prediction
from app.domain.entities.prediction_reason import PredictionReason
from app.domain.entities.search import CallSearchCriteria
from app.infrastructure.database.connection import Database
from app.infrastructure.database.query import (
    Column,
    Filter,
    FilterGroup,
    LateralJoin,
    Sort,
)


class PostgresCallService:
    """Loads and searches calls through PostgreSQL."""

    def __init__(self, database: Database):
        self._database = database

    def get_by_id(self, call_id: UUID) -> Call | None:
        row = self._database.select_one(
            "public.calls",
            _CALL_FIELDS,
            alias="c",
            joins=(_LATEST_ASSESSMENT_JOIN,),
            filters=(Filter("c.id", "=", call_id),),
        )

        if row is None:
            return None

        return Call(
            id=row[0],
            call_type=row[1],
            imsi_a=_imsi_from_database(row[2]),
            msisdn_a=row[3],
            msisdn_b=row[4],
            call_time=row[5],
            duration_seconds=row[6],
            msisdn_c=row[7],
            assessment=_assessment_from_row(row, row[0]),
        )

    def list(self, criteria: CallSearchCriteria) -> Page[Call]:
        filters = []
        if criteria.date_from is not None:
            filters.append(Filter("c.call_time", ">=", criteria.date_from))
        if criteria.date_to_exclusive is not None:
            filters.append(Filter("c.call_time", "<", criteria.date_to_exclusive))
        elif criteria.date_to is not None:
            filters.append(Filter("c.call_time", "<=", criteria.date_to))
        if criteria.call_type is not None:
            filters.append(Filter("c.call_type", "=", criteria.call_type.value))
        if criteria.msisdn is not None:
            filters.append(
                FilterGroup(
                    (
                        Filter("c.msisdn_a", "=", criteria.msisdn),
                        Filter("c.msisdn_b", "=", criteria.msisdn),
                        Filter("c.msisdn_c", "=", criteria.msisdn),
                    )
                )
            )
        if criteria.risk_level is not None:
            filters.append(Filter("a.risk_level", "=", criteria.risk_level.value))

        offset = (criteria.page - 1) * criteria.page_size
        total = self._database.count(
            "public.calls",
            alias="c",
            joins=(_LATEST_ASSESSMENT_JOIN,),
            filters=filters,
        )
        rows = self._database.select_all(
            "public.calls",
            _CALL_FIELDS,
            alias="c",
            joins=(_LATEST_ASSESSMENT_JOIN,),
            filters=filters,
            order_by=(Sort("c.call_time", "DESC"), Sort("c.id", "DESC")),
            limit=criteria.page_size,
            offset=offset,
        )

        items = tuple(
            Call(
                id=row[0],
                call_type=row[1],
                imsi_a=_imsi_from_database(row[2]),
                msisdn_a=row[3],
                msisdn_b=row[4],
                call_time=row[5],
                duration_seconds=row[6],
                msisdn_c=row[7],
                assessment=_assessment_from_row(row, row[0]),
            )
            for row in rows
        )
        return Page(
            items=items,
            page=criteria.page,
            page_size=criteria.page_size,
            total=total,
        )

    def history_before(self, call: Call) -> tuple[Call, ...]:
        """Return prior calls involving any number in the current call."""
        parties = (call.msisdn_a, call.msisdn_b, call.msisdn_c)
        party_filters = tuple(
            Filter(f"c.{field}", "=", number)
            for field in ("msisdn_a", "msisdn_b", "msisdn_c")
            for number in parties
            if number is not None
        )
        rows = self._database.select_all(
            "public.calls",
            _HISTORY_FIELDS,
            alias="c",
            filters=(
                Filter("c.call_time", "<", call.call_time),
                FilterGroup(party_filters),
            ),
            order_by=(Sort("c.call_time", "ASC"), Sort("c.id", "ASC")),
        )
        return tuple(
            Call(
                id=row[0],
                call_type=row[1],
                imsi_a=_imsi_from_database(row[2]),
                msisdn_a=row[3],
                msisdn_b=row[4],
                call_time=row[5],
                duration_seconds=row[6],
                msisdn_c=row[7],
            )
            for row in rows
        )


_CALL_FIELDS = (
    "c.id",
    "c.call_type",
    "c.imsi_a",
    "c.msisdn_a",
    "c.msisdn_b",
    "c.call_time",
    "c.duration_seconds",
    "c.msisdn_c",
    "a.risk_score",
    "a.risk_level",
    "a.is_fraud",
    "a.fraud_scenario",
    "a.reasons",
    "a.recommendation",
    "a.auto_blocked",
)

_HISTORY_FIELDS = (
    "c.id",
    "c.call_type",
    "c.imsi_a",
    "c.msisdn_a",
    "c.msisdn_b",
    "c.call_time",
    "c.duration_seconds",
    "c.msisdn_c",
)

_LATEST_ASSESSMENT_JOIN = LateralJoin(
    table="public.call_risk_assessments",
    alias="a",
    fields=(
        "risk_score",
        "risk_level",
        "is_fraud",
        "fraud_scenario",
        "reasons",
        "recommendation",
        "auto_blocked",
    ),
    filters=(Filter("call_id", "=", Column("c.id")),),
    order_by=(Sort("assessed_at", "DESC"), Sort("id", "DESC")),
    limit=1,
)


def _imsi_from_database(value: object) -> str | None:
    """Treat malformed legacy IMSI values as missing when reading calls."""
    if not isinstance(value, str) or not value.strip() or len(value) > 32:
        return None
    return value


def _assessment_from_row(row, call_id: UUID) -> Prediction | None:
    if row[8] is None:
        return None
    raw_reasons = row[12]
    if isinstance(raw_reasons, str):
        raw_reasons = json.loads(raw_reasons)
    reasons = tuple(PredictionReason(**reason) for reason in (raw_reasons or []))
    return Prediction(
        call_id=call_id,
        risk_score=row[8],
        risk_level=row[9],
        is_fraud=row[10],
        fraud_scenario=row[11],
        reasons=reasons,
        recommendation=row[13],
        auto_blocked=row[14],
    )
