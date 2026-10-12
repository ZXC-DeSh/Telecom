from app.infrastructure.database.connection import Database


class PostgresDatabaseHealthService:
    def __init__(self, database: Database) -> None:
        self._database = database

    def is_database_available(self) -> bool:
        return self._database.ping()
