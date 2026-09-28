import re
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


def normalize_number(value: str) -> str:
    """Exact dialled numbers only; no substring matching or extension stripping."""
    number = re.sub(r"[ ()-]", "", value.strip())
    if re.fullmatch(r"test:[a-zA-Z0-9_]+", number):
        return number  # Non-dialable namespace for generated fixtures.
    if re.fullmatch(r"[0-9]{3}", number):
        return number
    if re.fullmatch(r"8[0-9]{10}", number):
        number = "+7" + number[1:]
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", number):
        raise ValueError("Expected E.164, a three-digit service code, or test:<id>")
    return number


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class CallStart(StrictModel):
    call_id: str = Field(min_length=1, max_length=100)
    caller: str
    callee: str
    started_at: AwareDatetime
    subscriber_id: str = Field(min_length=1, max_length=100)
    source_country: str = Field(pattern=r"^[A-Z]{2}$")
    source_operator: str = Field(min_length=1, max_length=100)
    ingress_trunk: str = Field(min_length=1, max_length=100)
    destination_region: str = Field(min_length=1, max_length=100)
    connection_type: Literal["mobile", "fixed", "voip"]
    caller_identity_verified: bool = False
    # Both fields must come from authenticated operator signalling, not caller ID.
    destination_service: Literal["ordinary", "emergency"] = "ordinary"

    @field_validator("caller", "callee")
    @classmethod
    def number(cls, value: str) -> str:
        return normalize_number(value)


class CompletedCall(CallStart):
    ended_at: AwareDatetime
    observed_at: AwareDatetime
    duration_seconds: float = Field(ge=0, le=86400)
    answered: bool

    @model_validator(mode="after")
    def chronology(self):
        if self.ended_at < self.started_at or self.observed_at < self.ended_at:
            raise ValueError("Require started_at <= ended_at <= observed_at")
        if self.duration_seconds > (self.ended_at - self.started_at).total_seconds():
            raise ValueError("Duration exceeds the call interval")
        if not self.answered and self.duration_seconds != 0:
            raise ValueError("Unanswered call must have zero conversation duration")
        return self


class NumberQuery(StrictModel):
    number: str
    at: AwareDatetime

    @field_validator("number")
    @classmethod
    def number_format(cls, value: str) -> str:
        return normalize_number(value)


class PrivilegeRequest(StrictModel):
    number: str
    justification: str = Field(min_length=10, max_length=2000)

    @field_validator("number")
    @classmethod
    def number_format(cls, value: str) -> str:
        return normalize_number(value)


class Approval(StrictModel):
    verified_subscriber_id: str = Field(min_length=1, max_length=100)
    verified_operator: str = Field(min_length=1, max_length=100)
    verified_trunk: str = Field(min_length=1, max_length=100)
    evidence_reference: str = Field(min_length=5, max_length=500)
    expires_at: AwareDatetime


class Revocation(StrictModel):
    reason: str = Field(min_length=5, max_length=1000)
