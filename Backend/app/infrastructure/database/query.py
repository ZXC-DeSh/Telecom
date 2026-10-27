from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class CurrentTimestamp:
    """A request for PostgreSQL's transaction timestamp in a write value."""


@dataclass(frozen=True, slots=True)
class Filter:
    field: str
    operator: Literal["=", "!=", ">", ">=", "<", "<=", "LIKE", "ILIKE", "IN", "~", "!~"]
    value: object


@dataclass(frozen=True, slots=True)
class FilterGroup:
    filters: tuple[Filter | FilterGroup, ...]
    operator: Literal["AND", "OR"] = "OR"


@dataclass(frozen=True, slots=True)
class Sort:
    field: str
    direction: Literal["ASC", "DESC"] = "ASC"
