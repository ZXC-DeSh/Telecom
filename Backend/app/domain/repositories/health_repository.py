from typing import Protocol


class DatabaseReadiness(Protocol):
    def is_database_available(self) -> bool: ...
