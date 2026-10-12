from app.domain.entities.call import Call
from app.domain.entities.page import Page
from app.domain.entities.search import CallSearchCriteria
from app.domain.repositories.calls import CallRepository


class ListCalls:
    def __init__(self, calls: CallRepository):
        self._calls = calls

    def execute(self, criteria: CallSearchCriteria) -> Page[Call]:
        return self._calls.list(criteria)
