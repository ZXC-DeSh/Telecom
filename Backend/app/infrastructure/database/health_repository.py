from app.infrastructure.database.connection import Database


class HealthRepository:
    """PostgreSQL adapter for the database health check port."""

    def __init__(self, database: Database):
        self._database = database

    def is_database_available(self) -> bool:
        with self._database.connect() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)
