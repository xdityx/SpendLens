from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEVELOPMENT_API_TOKEN = "spendlens-local-development-api-token"


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    database_url: str = "postgresql+psycopg://spendlens:spendlens@localhost:5432/spendlens"
    api_title: str = "SpendLens API"
    api_version: str = "0.1.0"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    app_timezone: str = "Asia/Kolkata"
    app_environment: Literal["development", "production"] = "development"
    spendlens_api_token: str = Field(default=DEVELOPMENT_API_TOKEN, min_length=32)

    @field_validator("database_url", mode="before")
    @classmethod
    def use_psycopg_driver(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_environment == "production" and self.spendlens_api_token == DEVELOPMENT_API_TOKEN:
            raise ValueError("Production requires a unique SPENDLENS_API_TOKEN")
        return self

    @property
    def cors_allowed_origins(self) -> list[str]:
        """Return explicit CORS origins parsed from a comma-separated setting."""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def app_zoneinfo(self) -> ZoneInfo:
        """Return the configured IANA application timezone."""

        try:
            return ZoneInfo(self.app_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Invalid APP_TIMEZONE configured: {self.app_timezone}") from exc

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
