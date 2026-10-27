from dataclasses import dataclass
from datetime import datetime

from app.domain.value_objects import CallType, FraudScenario, RiskLevel


@dataclass(frozen=True, slots=True)
class CallSearchCriteria:
    page: int
    page_size: int
    date_from: datetime | None = None
    date_to: datetime | None = None
    date_to_exclusive: datetime | None = None
    call_type: CallType | None = None
    msisdn: str | None = None
    risk_level: RiskLevel | None = None

    def __post_init__(self) -> None:
        _validate_pagination(self.page, self.page_size)
        _validate_dates(self.date_from, self.date_to)
        if self.date_to_exclusive is not None:
            if self.date_to_exclusive.utcoffset() is not None:
                raise ValueError("даты фильтра не должны содержать часовой пояс")
            if self.date_from is not None and self.date_to_exclusive <= self.date_from:
                raise ValueError("date_to_exclusive должен быть позже date_from")
        if self.msisdn is not None and not _is_msisdn(self.msisdn):
            raise ValueError("msisdn должен содержать 10 цифр")


@dataclass(frozen=True, slots=True)
class FraudAlertSearchCriteria:
    page: int
    page_size: int
    risk_level: RiskLevel | None = None
    fraud_scenario: FraudScenario | None = None
    msisdn: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None

    def __post_init__(self) -> None:
        _validate_pagination(self.page, self.page_size)
        _validate_dates(self.date_from, self.date_to)
        if self.msisdn is not None and not _is_msisdn(self.msisdn):
            raise ValueError("msisdn должен содержать 10 цифр")


def _validate_pagination(page: int, page_size: int) -> None:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("недопустимые параметры пагинации")


def _validate_dates(date_from: datetime | None, date_to: datetime | None) -> None:
    for value in (date_from, date_to):
        if value is not None and value.utcoffset() is not None:
            raise ValueError("даты фильтра не должны содержать часовой пояс")
    if date_from is not None and date_to is not None and date_to < date_from:
        raise ValueError("date_to должен быть не раньше date_from")


def _is_msisdn(value: str) -> bool:
    return len(value) == 10 and value.isascii() and value.isdigit()
