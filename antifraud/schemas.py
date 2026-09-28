import re
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


def normalize_number(value: str) -> str:
    """Точное сопоставление набранного номера без поиска подстрок и удаления добавочных цифр."""
    number = re.sub(r"[ ()-]", "", value.strip())
    if re.fullmatch(r"test:[a-zA-Z0-9_]+", number):
        return number  # Недозваниваемые идентификаторы для синтетических примеров.
    if re.fullmatch(r"[0-9]{3}", number):
        return number
    if re.fullmatch(r"8[0-9]{10}", number):
        number = "+7" + number[1:]
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", number):
        raise ValueError("Введите номер в формате +7…, трёхзначный код службы или test:<идентификатор>")
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
    # Подтверждение источника и тип назначения поступают от оператора, а не из отображаемого номера.
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
            raise ValueError("Время начала не может быть позже окончания, а окончание — позже получения записи")
        if self.duration_seconds > (self.ended_at - self.started_at).total_seconds():
            raise ValueError("Длительность разговора превышает интервал соединения")
        if not self.answered and self.duration_seconds != 0:
            raise ValueError("У неотвеченного вызова длительность разговора должна быть нулевой")
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


class RegistryNumber(StrictModel):
    number: str
    organization: str = Field(min_length=2, max_length=150)

    @field_validator("number")
    @classmethod
    def number_format(cls, value: str) -> str:
        return normalize_number(value)

    @field_validator("organization")
    @classmethod
    def organization_name(cls, value: str) -> str:
        if len(value.strip()) < 2:
            raise ValueError("Укажите название организации")
        return value.strip()
