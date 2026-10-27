from uuid import UUID

from app.application.exceptions import EntityNotFound
from app.domain.entities.call import Call
from app.domain.repositories.calls import CallRepository


class GetCall:
    def __init__(self, calls: CallRepository):
        self._calls = calls

    def execute(self, call_id: UUID) -> Call:
        call = self._calls.get_by_id(call_id)
        if call is None:
            raise EntityNotFound(f"Вызов с идентификатором {call_id} не найден")
        return call
