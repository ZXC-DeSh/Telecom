from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ServiceHealth:
    database_available: bool
    model_available: bool

    def __post_init__(self) -> None:
        if not isinstance(self.database_available, bool) or not isinstance(
            self.model_available, bool
        ):
            raise TypeError("состояния компонентов должны быть логическими значениями")

    @property
    def is_healthy(self) -> bool:
        return self.database_available and self.model_available
