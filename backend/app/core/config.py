from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    database_url: str = "postgresql+psycopg://spendlens:spendlens@localhost:5432/spendlens"
    api_title: str = "SpendLens API"
    api_version: str = "0.1.0"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_allowed_origins(self) -> list[str]:
        """Return explicit CORS origins parsed from a comma-separated setting."""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
