from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    status_code: int = Field(ge=100, le=599)
    message: str
    data: T | None = None
