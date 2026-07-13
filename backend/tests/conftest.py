import os
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("SPENDLENS_API_TOKEN", "spendlens-local-development-api-token")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


def _session_factory() -> tuple[object, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine, TestingSessionLocal = _session_factory()

    with TestingSessionLocal() as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def api_client() -> Generator[TestClient, None, None]:
    engine, TestingSessionLocal = _session_factory()

    def override_get_db() -> Generator[Session, None, None]:
        with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, headers={"Authorization": "Bearer spendlens-local-development-api-token"}) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)

    Base.metadata.drop_all(engine)
    engine.dispose()
