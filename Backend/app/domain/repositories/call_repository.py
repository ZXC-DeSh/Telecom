from typing import Protocol

from app.domain.entities.call import Call
from app.domain.entities.page import Page
from app.domain.entities.search import CallSearchCriteria


class CallRepository(Protocol):
    """Persistence port required by call use cases."""

    def get_by_id(self, call_id: int) -> Call | None: ...

    def list(self, criteria: CallSearchCriteria) -> Page[Call]: ...
