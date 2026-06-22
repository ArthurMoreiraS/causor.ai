"""SQLAlchemy engine / session management for the System of Record."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.settings import settings


class Base(DeclarativeBase):
    """Declarative base for all SOR models."""


def _connect_args(database_url: str) -> dict:
    if database_url.startswith("postgresql+psycopg"):
        # Supabase's transaction pooler can reuse server-side prepared statement
        # names across clients. Disabling psycopg prepared statements avoids
        # DuplicatePreparedStatement during local/demo traffic.
        return {"prepare_threshold": None}
    return {}


engine = create_engine(
    settings.database_url,
    future=True,
    connect_args=_connect_args(settings.database_url),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI-style dependency yielding a session and closing it afterwards."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
