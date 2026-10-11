from collections.abc import Iterator
from contextlib import contextmanager
import psycopg2
from psycopg2.extensions import connection

from app.core.config import Settings


class Database:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._closed = False

    def close(self) -> None:
        self._closed = True

    @contextmanager
    def connect(self) -> Iterator[connection]:
        if self._closed:
            raise RuntimeError("Database is closed")

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

