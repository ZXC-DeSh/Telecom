from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class Column:
    """A column reference used as a filter value instead of a bound value."""

    name: str


@dataclass(frozen=True, slots=True)
class CurrentTimestamp:
    """A request for PostgreSQL's transaction timestamp in a write value."""


@dataclass(frozen=True, slots=True)
class Filter:
    field: str
    operator: Literal["=", "!=", ">", ">=", "<", "<=", "LIKE", "ILIKE", "IN"]
    value: object


@dataclass(frozen=True, slots=True)
class FilterGroup:
    filters: tuple[Filter | FilterGroup, ...]
    operator: Literal["AND", "OR"] = "OR"


@dataclass(frozen=True, slots=True)
class Sort:
    field: str
    direction: Literal["ASC", "DESC"] = "ASC"


@dataclass(frozen=True, slots=True)
class LateralJoin:
    table: str
    alias: str
    fields: tuple[str, ...]
    filters: tuple[Filter | FilterGroup, ...]
    order_by: tuple[Sort, ...]
    limit: int = 1
    kind: Literal["LEFT", "INNER"] = "LEFT"
