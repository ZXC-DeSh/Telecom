from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any, Literal, overload

import psycopg2
from psycopg2.extensions import connection
from psycopg2.extras import register_uuid
from psycopg2.sql import SQL, Composable, Identifier

from app.core.config import Settings
from app.infrastructure.database.query import (
    CurrentTimestamp,
    Filter,
    FilterGroup,
    Sort,
)

register_uuid()


class Database:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._closed = False

    def close(self) -> None:
        self._closed = True

    def ping(self) -> bool:
        with self.connect() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)

    def refresh_dashboard_summary_cache(self) -> None:
        with self.connect() as conn, conn.cursor() as cursor:
            cursor.execute(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY "
                "public.dashboard_summary_cache"
            )
            conn.commit()

    def select_one(
        self,
        table: str,
        fields: Sequence[str],
        *,
        filters: Sequence[Filter | FilterGroup] = (),
        order_by: Sequence[Sort] = (),
        alias: str | None = None,
    ) -> tuple[Any, ...] | None:
        query, params = self._select_query(
            table, fields, filters, order_by, alias=alias, limit=1
        )
        with self.connect() as conn, conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    def select_all(
        self,
        table: str,
        fields: Sequence[str],
        *,
        filters: Sequence[Filter | FilterGroup] = (),
        order_by: Sequence[Sort] = (),
        limit: int | None = None,
        offset: int | None = None,
        alias: str | None = None,
    ) -> list[tuple[Any, ...]]:
        query, params = self._select_query(
            table,
            fields,
            filters,
            order_by,
            alias=alias,
            limit=limit,
            offset=offset,
        )
        with self.connect() as conn, conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def select_recent_calls_with_latest_assessment(
        self,
        fields: Sequence[str],
        *,
        filters: Sequence[Filter | FilterGroup] = (),
        order_by: Sequence[Sort] = (),
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[tuple[Any, ...]]:
        assessment_fields = {
            "c.risk_score": "a.risk_score",
            "c.risk_level": "a.risk_level",
            "c.is_fraud": "a.is_fraud",
            "c.fraud_scenario": "a.fraud_scenario",
            "c.reasons": "a.reasons",
            "c.recommendation": "a.recommendation",
            "c.auto_blocked": "a.auto_blocked",
        }
        call_filters = tuple(
            filter_
            for filter_ in filters
            if not (isinstance(filter_, Filter) and filter_.field == "c.risk_level")
        )
        assessment_filters = tuple(
            filter_
            for filter_ in filters
            if isinstance(filter_, Filter) and filter_.field == "c.risk_level"
        )
        query = SQL(
            "WITH recent_calls AS ("
            " SELECT c.id, c.call_type, c.imsi_a, c.msisdn_a, c.msisdn_b, c.call_time, "
            " c.duration_seconds, c.msisdn_c FROM public.calls AS c"
        )
        params: tuple[object, ...] = ()
        if call_filters:
            where, params = self._where(call_filters)
            query += SQL(" WHERE ") + where
        query += SQL(
            " ORDER BY c.call_time DESC, c.id DESC LIMIT %s OFFSET %s"
            ") SELECT {} FROM recent_calls AS c LEFT JOIN LATERAL ("
            " SELECT risk_score, risk_level, is_fraud, fraud_scenario, reasons, "
            " recommendation, auto_blocked FROM public.call_risk_assessments AS a "
            " WHERE a.call_id = c.id ORDER BY a.assessed_at DESC, a.id DESC LIMIT 1"
            ") AS a ON true"
        ).format(
            SQL(", ").join(
                self._identifier(assessment_fields.get(field, field))
                for field in fields
            )
        )
        params += (limit or 100, offset or 0)
        if assessment_filters:
            mapped_filters = tuple(
                self._map_assessment_filter(filter_) for filter_ in assessment_filters
            )
            where, filter_params = self._where(mapped_filters)
            query += SQL(" WHERE ") + where
            params += filter_params
        if order_by:
            query += SQL(" ORDER BY ") + SQL(", ").join(
                SQL("{} {}").format(
                    self._identifier(sort.field), self._sort_direction(sort.direction)
                )
                for sort in order_by
            )
        with self.connect() as conn, conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    @classmethod
    def _map_assessment_filter(
        cls, filter_: Filter | FilterGroup
    ) -> Filter | FilterGroup:
        assessment_fields = {
            "c.risk_score": "a.risk_score",
            "c.risk_level": "a.risk_level",
            "c.is_fraud": "a.is_fraud",
            "c.fraud_scenario": "a.fraud_scenario",
            "c.reasons": "a.reasons",
            "c.recommendation": "a.recommendation",
            "c.auto_blocked": "a.auto_blocked",
        }
        if isinstance(filter_, FilterGroup):
            return FilterGroup(
                tuple(cls._map_assessment_filter(child) for child in filter_.filters),
                operator=filter_.operator,
            )
        return Filter(
            assessment_fields.get(filter_.field, filter_.field),
            filter_.operator,
            filter_.value,
        )

    def count(
        self,
        table: str,
        *,
        filters: Sequence[Filter | FilterGroup] = (),
        alias: str | None = None,
    ) -> int:
        query, params = self._select_query(
            table, ("count(*)",), filters, (), alias=alias
        )
        with self.connect() as conn, conn.cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("подсчёт строк не вернул результат")
        return row[0]

    def insert(
        self,
        table: str,
        values: Mapping[str, object],
        *,
        returning: Sequence[str] = (),
    ) -> tuple[Any, ...] | None:
        if not values:
            raise ValueError("для вставки требуется хотя бы одно значение")
        columns = tuple(values)
        value_sql, params = self._values(values)
        query = SQL("INSERT INTO {} ({}) VALUES ({})").format(
            self._identifier(table),
            SQL(", ").join(self._identifier(column) for column in columns),
            value_sql,
        )
        query = self._with_returning(query, returning)
        return self._write(query, params, returning=True)

    def update(
        self,
        table: str,
        values: Mapping[str, object],
        *,
        filters: Sequence[Filter | FilterGroup],
    ) -> int:
        if not filters or not values:
            raise ValueError("для обновления нужны значения и хотя бы один фильтр")
        where, params = self._where(filters)
        assignments, value_params = self._assignments(values)
        query = SQL("UPDATE {} SET {} WHERE {}").format(
            self._identifier(table),
            assignments,
            where,
        )
        return self._write(query, (*value_params, *params))

    def upsert(
        self,
        table: str,
        values: Mapping[str, object],
        *,
        conflict_fields: Sequence[str],
        update_fields: Sequence[str],
        returning: Sequence[str] = (),
    ) -> tuple[Any, ...] | None:
        if not values or not conflict_fields:
            raise ValueError(
                "для добавления или обновления нужны значения и поля конфликта"
            )
        if not set(update_fields).issubset(values):
            raise ValueError(
                "поля обновления должны присутствовать среди переданных значений"
            )
        columns = tuple(values)
        value_sql, params = self._values(values)
        query = SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({})").format(
            self._identifier(table),
            SQL(", ").join(self._identifier(column) for column in columns),
            value_sql,
            SQL(", ").join(self._identifier(column) for column in conflict_fields),
        )
        if update_fields:
            query += SQL(" DO UPDATE SET {} ").format(
                SQL(", ").join(
                    SQL("{} = EXCLUDED.{}").format(
                        self._identifier(column), self._identifier(column)
                    )
                    for column in update_fields
                )
            )
        else:
            query += SQL(" DO NOTHING")
        query = self._with_returning(query, returning)
        return self._write(query, params, returning=True)

    def _values(
        self, values: Mapping[str, object]
    ) -> tuple[Composable, tuple[object, ...]]:
        placeholders: list[Composable] = []
        params: list[object] = []
        for value in values.values():
            if isinstance(value, CurrentTimestamp):
                placeholders.append(SQL("now()"))
            else:
                placeholders.append(SQL("%s"))
                params.append(value)
        return SQL(", ").join(placeholders), tuple(params)

    def _assignments(
        self, values: Mapping[str, object]
    ) -> tuple[Composable, tuple[object, ...]]:
        clauses: list[Composable] = []
        params: list[object] = []
        for column, value in values.items():
            identifier = self._identifier(column)
            if isinstance(value, CurrentTimestamp):
                clauses.append(SQL("{} = now()").format(identifier))
            else:
                clauses.append(SQL("{} = %s").format(identifier))
                params.append(value)
        return SQL(", ").join(clauses), tuple(params)

    def _select_query(
        self,
        table: str,
        fields: Sequence[str],
        filters: Sequence[Filter | FilterGroup],
        order_by: Sequence[Sort],
        *,
        alias: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[Composable, tuple[object, ...]]:
        source = (
            SQL("{} AS {}").format(self._identifier(table), self._identifier(alias))
            if alias
            else self._identifier(table)
        )
        query = SQL("SELECT {} FROM {}").format(
            SQL(", ").join(
                SQL("count(*)") if field == "count(*)" else self._identifier(field)
                for field in fields
            ),
            source,
        )
        params: tuple[object, ...] = ()
        if filters:
            where, filter_params = self._where(filters)
            query += SQL(" WHERE ") + where
            params += filter_params
        if order_by:
            query += SQL(" ORDER BY ") + SQL(", ").join(
                SQL("{} {}").format(
                    self._identifier(sort.field),
                    self._sort_direction(sort.direction),
                )
                for sort in order_by
            )
        if limit is not None:
            query += SQL(" LIMIT %s")
            params += (limit,)
        if offset is not None:
            query += SQL(" OFFSET %s")
            params += (offset,)
        return query, params

    def _where(
        self, filters: Sequence[Filter | FilterGroup]
    ) -> tuple[Composable, tuple[object, ...]]:
        clauses: list[Composable] = []
        params: list[object] = []
        for filter_ in filters:
            clause, values = self._filter_clause(filter_)
            clauses.append(clause)
            params.extend(values)
        return SQL(" AND ").join(clauses), tuple(params)

    def _filter_clause(
        self, filter_: Filter | FilterGroup
    ) -> tuple[Composable, tuple[object, ...]]:
        if isinstance(filter_, FilterGroup):
            parts: list[Composable] = []
            params: list[object] = []
            for child in filter_.filters:
                clause, values = self._filter_clause(child)
                parts.append(clause)
                params.extend(values)
            if filter_.operator not in ("AND", "OR"):
                raise ValueError(
                    f"Недопустимый оператор группы фильтров: {filter_.operator}"
                )
            operator = SQL(filter_.operator)
            return SQL("({})").format(SQL(f" {filter_.operator} ").join(parts)), tuple(
                params
            )

        field = self._identifier(filter_.field)
        operator_name = filter_.operator
        operator = self._filter_operator(operator_name)
        value = filter_.value
        if value is None and operator_name in ("=", "!="):
            return SQL("{} IS {}NULL").format(
                field, SQL("NOT ") if operator_name == "!=" else SQL("")
            ), ()
        if operator_name == "IN":
            values = (
                tuple(value)
                if isinstance(value, Sequence) and not isinstance(value, (str, bytes))
                else (value,)
            )
            if not values:
                return SQL("FALSE"), ()
            return SQL("{} IN ({})").format(
                field, SQL(", ").join(SQL("%s") for _ in values)
            ), values
        return SQL("{} {} %s").format(field, operator), (value,)

    @staticmethod
    def _filter_operator(operator: str) -> SQL:
        if operator not in (
            "=",
            "!=",
            ">",
            ">=",
            "<",
            "<=",
            "LIKE",
            "ILIKE",
            "IN",
            "~",
            "!~",
        ):
            raise ValueError(f"Недопустимый оператор фильтра: {operator}")
        return SQL(operator)

    @staticmethod
    def _sort_direction(direction: str) -> SQL:
        if direction not in ("ASC", "DESC"):
            raise ValueError(f"Недопустимое направление сортировки: {direction}")
        return SQL(direction)

    def _with_returning(self, query: Composable, fields: Sequence[str]) -> Composable:
        if not fields:
            return query
        return (
            query
            + SQL(" RETURNING ")
            + SQL(", ").join(self._identifier(field) for field in fields)
        )

    @staticmethod
    def _identifier(name: str) -> Identifier:
        return Identifier(*name.split("."))

    @overload
    def _write(
        self,
        query: Composable,
        params: Sequence[object],
        *,
        returning: Literal[True],
    ) -> tuple[Any, ...] | None: ...

    @overload
    def _write(
        self,
        query: Composable,
        params: Sequence[object],
        *,
        returning: Literal[False] = False,
    ) -> int: ...

    def _write(
        self,
        query: Composable,
        params: Sequence[object],
        *,
        returning: bool = False,
    ) -> tuple[Any, ...] | int | None:
        with self.connect() as conn, conn.cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone() if returning and cursor.description else None
            rowcount = cursor.rowcount
            conn.commit()
            return result if returning else rowcount

    @contextmanager
    def connect(self) -> Iterator[connection]:
        if self._closed:
            raise RuntimeError("соединение с базой данных закрыто")

        conn = psycopg2.connect(
            host=self._settings.db_host,
            port=self._settings.db_port,
            dbname=self._settings.db_name,
            user=self._settings.db_user,
            password=self._settings.db_password,
            connect_timeout=self._settings.db_connect_timeout,
        )

        try:
            yield conn
        finally:
            conn.close()
