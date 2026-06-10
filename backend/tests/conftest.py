"""Shared pytest fixtures.

Tests run against an in-memory SQLite database so the suite is fast and
hermetic. Models must avoid Postgres-only column types in the core path, or
guard them, so the same metadata works on SQLite for unit tests.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.sor.db import Base

# Import models so they register on Base.metadata before create_all.
import app.sor.models  # noqa: F401,E402


@pytest.fixture
def db_session() -> Iterator[Session]:
    # StaticPool + check_same_thread=False keeps a single shared connection so
    # the in-memory DB survives across the TestClient request thread.
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
