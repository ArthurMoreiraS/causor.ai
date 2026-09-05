"""Explicit, disposable PostgreSQL schemas; never uses the application DB URL."""

import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


def migrate(engine, revision="head", *, downgrade=False):
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        (command.downgrade if downgrade else command.upgrade)(config, revision)


@pytest.fixture
def pg_engine():
    raw_url = os.environ.get("CAUSOR_TEST_POSTGRES_URL")
    if not raw_url:
        pytest.skip("Set CAUSOR_TEST_POSTGRES_URL to the disposable CI database")
    url = make_url(raw_url)
    if url.host not in {"localhost", "127.0.0.1"} or url.database != "causor_test":
        pytest.fail("Postgres tests require localhost/causor_test; refusing another database")
    schema = "causor_test_" + uuid4().hex
    admin = create_engine(url, connect_args={"prepare_threshold": None})
    engine = None
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={
            "prepare_threshold": None,
            "options": f"-csearch_path={schema} -cstatement_timeout=10000 -clock_timeout=2000",
        })
        migrate(engine)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        # Only the exact randomly generated test schema is removed.
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def db_session(pg_engine):
    """Run reusable API/seed scenarios against real FK constraints and triggers."""
    with Session(pg_engine, autoflush=False, expire_on_commit=False) as session:
        yield session
