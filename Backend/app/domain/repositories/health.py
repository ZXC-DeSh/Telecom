from typing import Protocol


class DatabaseReadinessRepository(Protocol):
    def is_database_available(self) -> bool: ...


class ModelReadinessRepository(Protocol):
    def is_available(self) -> bool: ...
