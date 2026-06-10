"""SQLAlchemy engine / session management for the System of Record."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.settings import settings


class Base(DeclarativeBase):
    """Declarative base for all SOR models."""


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI-style dependency yielding a session and closing it afterwards."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
