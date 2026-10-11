from app.application.exceptions import FeatureUnavailable
from app.domain.entities.call import Call
from app.domain.entities.page import Page
from app.domain.entities.search import CallSearchCriteria
from app.domain.repositories.call_repository import CallRepository
from app.infrastructure.database.connection import Database


class PostgresCallRepository(CallRepository):
    """PostgreSQL adapter for the domain call repository."""

    def __init__(self, database: Database):
        self._database = database

    def get_by_id(self, call_id: int) -> Call | None:
        query = """
            SELECT id, call_type, imsi_a, msisdn_a, msisdn_b,
                   call_time, duration_seconds, msisdn_c
            FROM public.calls
            WHERE id = %s
        """
        with self._database.connect() as conn, conn.cursor() as cursor:
            cursor.execute(query, (call_id,))
            row = cursor.fetchone()

        if row is None:
            return None

        return Call(
            id=row[0],
            call_type=row[1],
            imsi_a=row[2],
            msisdn_a=row[3],
            msisdn_b=row[4],
            call_time=row[5],
            duration_seconds=row[6],
            msisdn_c=row[7],
        )

    def list(self, criteria: CallSearchCriteria) -> Page[Call]:
        raise FeatureUnavailable(
            "Call listing requires an assessment query source that is not configured"
        )
