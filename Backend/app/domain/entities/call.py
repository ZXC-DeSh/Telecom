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
            raise ValueError("id must be a UUID")
        object.__setattr__(self, "call_type", CallType(self.call_type))
        if not isinstance(self.msisdn_a, str) or not self.msisdn_a:
            raise ValueError("caller and recipient numbers are required")
        if not isinstance(self.msisdn_b, str) or not self.msisdn_b:
            raise ValueError("caller and recipient numbers are required")
        if len(self.msisdn_a) > 20 or len(self.msisdn_b) > 20:
            raise ValueError("phone numbers cannot exceed 20 characters")
        if not re.fullmatch(r"[0-9]{10}", self.msisdn_a) or not re.fullmatch(
            r"[0-9]{10}", self.msisdn_b
        ):
            raise ValueError("caller and recipient numbers must contain 10 digits")
        if self.msisdn_c is not None and not isinstance(self.msisdn_c, str):
            raise ValueError("forwarding number must be a string")
        if self.msisdn_c is not None and len(self.msisdn_c) > 20:
            raise ValueError("forwarding number cannot exceed 20 characters")
        if self.msisdn_c is not None and not re.fullmatch(r"[0-9]{10}", self.msisdn_c):
            raise ValueError("forwarding number must contain 10 digits")
        if self.imsi_a is not None and (
            not isinstance(self.imsi_a, str) or not 1 <= len(self.imsi_a) <= 32
        ):
            raise ValueError("imsi_a must contain 1 to 32 characters")
        if self.call_type != CallType.FORWARDED and self.msisdn_c is not None:
            raise ValueError("forwarding number is only valid for forwarded calls")
        if self.call_type == CallType.FORWARDED and self.msisdn_c is None:
            raise ValueError("forwarding number is required for forwarded calls")
        if self.assessment is not None and not isinstance(self.assessment, Prediction):
            raise ValueError("assessment must be a Prediction")
        if (
            self.assessment is not None
            and self.id is not None
            and self.assessment.call_id not in (None, self.id)
        ):
            raise ValueError("assessment call_id must match call id")
        if (
            isinstance(self.duration_seconds, bool)
            or not isinstance(self.duration_seconds, (int, float))
            or not isfinite(self.duration_seconds)
            or self.duration_seconds < 0
        ):
            raise ValueError("duration_seconds must be finite and non-negative")
        if not isinstance(self.call_time, datetime):
            raise TypeError("call_time must be a datetime")
        if self.call_time.utcoffset() is not None:
            raise ValueError("call_time must not include a timezone")
