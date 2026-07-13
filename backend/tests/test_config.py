import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    ("database_url", "expected"),
    [
        (
            "postgres://user:password@database.example/spendlens",
            "postgresql+psycopg://user:password@database.example/spendlens",
        ),
        (
            "postgresql://user:password@database.example/spendlens",
            "postgresql+psycopg://user:password@database.example/spendlens",
        ),
    ],
)
def test_settings_normalize_driverless_postgres_urls(database_url: str, expected: str) -> None:
    settings = Settings(database_url=database_url)

    assert settings.database_url == expected


def test_settings_preserve_explicit_database_driver() -> None:
    database_url = "postgresql+psycopg://user:password@database.example/spendlens"

    settings = Settings(database_url=database_url)

    assert settings.database_url == database_url