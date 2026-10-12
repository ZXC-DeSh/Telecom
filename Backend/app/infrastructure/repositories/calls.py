from uuid import UUID

from app.domain.entities.call import Call
from app.domain.entities.page import Page
from app.domain.entities.search import CallSearchCriteria
from app.domain.repositories.calls import CallRepository
from app.infrastructure.services.call_service import PostgresCallService


class PostgresCallRepository(CallRepository):
    def __init__(self, service: PostgresCallService) -> None:
        self._service = service

    def get_by_id(self, call_id: UUID) -> Call | None:
        return self._service.get_by_id(call_id)

    def list(self, criteria: CallSearchCriteria) -> Page[Call]:
        return self._service.list(criteria)

    def history_before(self, call: Call) -> tuple[Call, ...]:
        return self._service.history_before(call)

