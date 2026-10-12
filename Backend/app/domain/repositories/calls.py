from typing import Protocol
from uuid import UUID

from app.domain.entities.call import Call
from app.domain.entities.page import Page
from app.domain.entities.search import CallSearchCriteria


class CallRepository(Protocol):
    def get_by_id(self, call_id: UUID) -> Call | None: ...

    def list(self, criteria: CallSearchCriteria) -> Page[Call]: ...

    def history_before(self, call: Call) -> tuple[Call, ...]: ...
