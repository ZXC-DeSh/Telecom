from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AntiFraude API"
    app_env: str = "local"
    log_level: str = "INFO"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "antifraude"
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_connect_timeout: int = 3
    cors_origins: str = ""
    api_prefix: str = "/api/v1"
    model_path: str = "models/FraudScope_r9.2.cbm"
    model_passport_path: str = "models/FraudScrope_r9.2.json"

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
