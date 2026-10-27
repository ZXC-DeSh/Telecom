from __future__ import annotations

import json
import logging
from uuid import UUID

from app.domain.entities.call import Call
from app.domain.entities.page import Page
from app.domain.entities.prediction import Prediction
from app.domain.entities.prediction_reason import PredictionReason
from app.domain.entities.search import CallSearchCriteria
from app.infrastructure.database.connection import Database
from app.infrastructure.database.query import (
    Filter,
    FilterGroup,
    Sort,
)

logger = logging.getLogger(__name__)
_PHONE_PATTERN = r"^[0-9]{10}$"


class CallService:
    def __init__(self, database: Database):
        self._database = database

    def get_by_id(self, call_id: UUID) -> Call | None:
        row = self._database.select_one(
            "public.calls_with_latest_assessment",
            _CALL_FIELDS,
            alias="c",
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
        return self._list(criteria, valid_numbers_only=False)

    def list_for_analysis(self, criteria: CallSearchCriteria) -> Page[Call]:
        if criteria.page == 1:
            self._log_invalid_analysis_calls(criteria)
        return self._list(criteria, valid_numbers_only=True)

    def _list(
        self, criteria: CallSearchCriteria, *, valid_numbers_only: bool
    ) -> Page[Call]:
        filters = self._search_filters(criteria)
        if valid_numbers_only:
            filters.extend(
                (
                    Filter("c.msisdn_a", "~", _PHONE_PATTERN),
                    Filter("c.msisdn_b", "~", _PHONE_PATTERN),
                    FilterGroup(
                        (
                            Filter("c.msisdn_c", "=", None),
                            Filter("c.msisdn_c", "~", _PHONE_PATTERN),
                        ),
                        operator="OR",
                    ),
                )
            )

        offset = (criteria.page - 1) * criteria.page_size
        count_filters = [
            filter_
            for filter_ in filters
            if not (
                isinstance(filter_, Filter)
                and filter_.field == "c.risk_level"
            )
        ]
        total = self._database.count(
            "public.calls",
            alias="c",
            filters=count_filters,
        )
        rows = self._database.select_recent_calls_with_latest_assessment(
            _CALL_FIELDS,
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

    @staticmethod
    def _search_filters(criteria: CallSearchCriteria) -> list[Filter | FilterGroup]:
        filters: list[Filter | FilterGroup] = []
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
            filters.append(Filter("c.risk_level", "=", criteria.risk_level.value))
        return filters

    def _log_invalid_analysis_calls(self, criteria: CallSearchCriteria) -> None:
        invalid_call = FilterGroup(
            (
                FilterGroup(
                    (
                        Filter("c.msisdn_a", "=", None),
                        Filter("c.msisdn_a", "!~", _PHONE_PATTERN),
                    )
                ),
                FilterGroup(
                    (
                        Filter("c.msisdn_b", "=", None),
                        Filter("c.msisdn_b", "!~", _PHONE_PATTERN),
                    )
                ),
                FilterGroup(
                    (
                        Filter("c.msisdn_c", "!=", None),
                        Filter("c.msisdn_c", "!~", _PHONE_PATTERN),
                    ),
                    operator="AND",
                ),
            )
        )
        rows = self._database.select_all(
            "public.calls_with_latest_assessment",
            ("c.id", "c.msisdn_a", "c.msisdn_b", "c.msisdn_c"),
            alias="c",
            filters=(*self._search_filters(criteria), invalid_call),
        )
        for call_id, msisdn_a, msisdn_b, msisdn_c in rows:
            invalid_fields = tuple(
                field
                for field, value in (
                    ("msisdn_a", msisdn_a),
                    ("msisdn_b", msisdn_b),
                    ("msisdn_c", msisdn_c),
                )
                if not _valid_phone_number(value, nullable=field == "msisdn_c")
            )
            logger.warning(
                "Skipping call with invalid phone number(s): call_id=%s fields=%s",
                call_id,
                ",".join(invalid_fields),
            )

    def history_before(self, call: Call) -> tuple[Call, ...]:
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
        valid_history: list[Call] = []
        for row in rows:
            try:
                valid_history.append(
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
                )
            except (TypeError, ValueError) as exc:
                logger.warning(
                    "Skipping invalid historical call: call_id=%s reason=%s",
                    row[0],
                    exc,
                )
        return tuple(valid_history)


_CALL_FIELDS = (
    "c.id",
    "c.call_type",
    "c.imsi_a",
    "c.msisdn_a",
    "c.msisdn_b",
    "c.call_time",
    "c.duration_seconds",
    "c.msisdn_c",
    "c.risk_score",
    "c.risk_level",
    "c.is_fraud",
    "c.fraud_scenario",
    "c.reasons",
    "c.recommendation",
    "c.auto_blocked",
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


def _valid_phone_number(value: object, *, nullable: bool = False) -> bool:
    if value is None:
        return nullable
    return (
        isinstance(value, str)
        and len(value) == 10
        and value.isascii()
        and value.isdigit()
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
