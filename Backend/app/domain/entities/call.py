import re
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from uuid import UUID

from app.domain.entities.prediction import Prediction
from app.domain.value_objects import CallType


@dataclass(frozen=True, slots=True)
class Call:
    id: UUID | None
    call_type: CallType
    msisdn_a: str
    msisdn_b: str
    call_time: datetime
    duration_seconds: float
    imsi_a: str | None = None
    msisdn_c: str | None = None
    assessment: Prediction | None = None

    def __post_init__(self) -> None:
        if self.id is not None and not isinstance(self.id, UUID):
            raise ValueError("id должен быть UUID")
        object.__setattr__(self, "call_type", CallType(self.call_type))
        if not isinstance(self.msisdn_a, str) or not self.msisdn_a:
            raise ValueError(
                f"необходимо указать номера вызывающего и принимающего абонентов (call_id={self.id})"
            )
        if not isinstance(self.msisdn_b, str) or not self.msisdn_b:
            raise ValueError(
                f"необходимо указать номера вызывающего и принимающего абонентов (call_id={self.id})"
            )
        if len(self.msisdn_a) > 20 or len(self.msisdn_b) > 20:
            raise ValueError("длина телефонных номеров не должна превышать 20 символов")
        if not re.fullmatch(r"[0-9]{10}", self.msisdn_a) or not re.fullmatch(
            r"[0-9]{10}", self.msisdn_b
        ):
            raise ValueError(
                "номера вызывающего и принимающего абонентов должны содержать 10 цифр "
                f"(call_id={self.id})"
            )
        if self.msisdn_c is not None and not isinstance(self.msisdn_c, str):
            raise ValueError("номер переадресации должен быть строкой")
        if self.msisdn_c is not None and len(self.msisdn_c) > 20:
            raise ValueError(
                "длина номера переадресации не должна превышать 20 символов"
            )
        if self.msisdn_c is not None and not re.fullmatch(r"[0-9]{10}", self.msisdn_c):
            raise ValueError("номер переадресации должен содержать 10 цифр")
        if self.imsi_a is not None and (
            not isinstance(self.imsi_a, str) or not 1 <= len(self.imsi_a) <= 32
        ):
            raise ValueError("imsi_a должен содержать от 1 до 32 символов")
        if self.call_type != CallType.FORWARDED and self.msisdn_c is not None:
            raise ValueError(
                "номер переадресации допустим только для переадресованных вызовов"
            )
        if self.call_type == CallType.FORWARDED and self.msisdn_c is None:
            raise ValueError(
                "для переадресованного вызова требуется номер переадресации"
            )
        if self.assessment is not None and not isinstance(self.assessment, Prediction):
            raise ValueError("оценка должна быть объектом Prediction")
        if (
            self.assessment is not None
            and self.id is not None
            and self.assessment.call_id not in (None, self.id)
        ):
            raise ValueError("call_id оценки должен совпадать с id вызова")
        if (
            isinstance(self.duration_seconds, bool)
            or not isinstance(self.duration_seconds, (int, float))
            or not isfinite(self.duration_seconds)
            or self.duration_seconds < 0
        ):
            raise ValueError(
                "duration_seconds должен быть конечным неотрицательным числом"
            )
        if not isinstance(self.call_time, datetime):
            raise TypeError("call_time должен иметь тип datetime")
        if self.call_time.utcoffset() is not None:
            raise ValueError("call_time не должен содержать часовой пояс")
