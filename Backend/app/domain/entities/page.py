from dataclasses import dataclass
from math import ceil
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    items: tuple[T, ...]
    page: int
    page_size: int
    total: int

    def __post_init__(self) -> None:
        if (
            type(self.page) is not int
            or type(self.page_size) is not int
            or type(self.total) is not int
            or self.page < 1
            or not 1 <= self.page_size <= 100
            or self.total < 0
        ):
            raise ValueError("недопустимые параметры пагинации")
        if len(self.items) > self.page_size:
            raise ValueError("число элементов страницы не может превышать page_size")
        if len(self.items) > self.total:
            raise ValueError("число элементов страницы не может превышать total")

    @property
    def pages(self) -> int:
        return ceil(self.total / self.page_size) if self.total else 0
