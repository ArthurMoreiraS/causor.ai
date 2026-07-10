"""Shared pytest fixtures.

Tests run against an in-memory SQLite database so the suite is fast and
hermetic. Models must avoid Postgres-only column types in the core path, or
guard them, so the same metadata works on SQLite for unit tests.
"""

from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import create_app
from app.auth.jwt_auth import CurrentUser, get_current_user
from app.sor.db import Base, get_session

# Import models so they register on Base.metadata before create_all.
import app.sor.models as models  # noqa: F401,E402


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


@pytest.fixture
def client(db_session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session

    def _current_user() -> CurrentUser:
        # Resolve a identidade da fixture `seeded` (primeiro escritório/usuário do
        # tenant semeado) em tempo de request, evitando JWT real nos testes de API.
        esc = db_session.scalars(
            select(models.Escritorio).order_by(models.Escritorio.id)
        ).first()
        usuario = (
            db_session.scalars(
                select(models.Usuario)
                .where(models.Usuario.escritorio_id == esc.id)
                .order_by(models.Usuario.id)
            ).first()
            if esc is not None
            else None
        )
        return CurrentUser(
            usuario_id=usuario.id if usuario is not None else 0,
            escritorio_id=esc.id if esc is not None else 0,
            email=usuario.email if usuario is not None else "test@x.com",
        )

    app.dependency_overrides[get_current_user] = _current_user
    return TestClient(app)


def seed_ready_context(db_session, processo):
    """Deixa o processo com ContextoProcesso ready/atual para testes que
    legitimamente redigem/protocolam (o gate fail-closed exige isso)."""
    from datetime import datetime, timezone

    from app.autos.context import current_fingerprint

    contexto = models.ContextoProcesso(
        escritorio_id=processo.escritorio_id,
        processo_id=processo.id,
        status="ready",
        source_fingerprint=current_fingerprint(db_session, processo=processo),
        inventario=[],
        cobertura={
            "documents_total": 0,
            "documents_extracted": 0,
            "documents_summarized": 0,
            "missing": [],
        },
        contexto_consolidado=None,
        citations=[],
        ready_at=datetime.now(timezone.utc),
    )
    db_session.add(contexto)
    db_session.flush()
    return contexto


def seed_filing_ready(db_session, peticao):
    """Contexto ready + fingerprint carimbado no dossiê da petição (gate de
    protocolo compara o fingerprint da minuta com o estado atual dos autos)."""
    contexto = seed_ready_context(db_session, peticao.processo)
    dossie = dict(peticao.dossie or {})
    dossie["source_fingerprint"] = contexto.source_fingerprint
    peticao.dossie = dossie
    db_session.flush()
    return contexto


@pytest.fixture
def seeded(db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()
    usuario = models.Usuario(
        escritorio_id=esc.id, nome="Adv Seed", email="seed@example.com",
        supabase_user_id="seed-sub",
    )
    db_session.add(usuario)
    db_session.flush()
    proc = models.Processo(escritorio_id=esc.id, numero="00000010020248260100", tribunal="TJSP")
    db_session.add(proc)
    db_session.flush()
    intimacao = models.Intimacao(
        processo_id=proc.id,
        escritorio_id=esc.id,
        fonte="DJEN",
        fonte_id="111",
        numero_processo="00000010020248260100",
        tipo_comunicacao="Intimação",
        data_disponibilizacao=date(2024, 9, 6),
        teor="Apresente contestacao em 15 dias uteis.",
    )
    db_session.add(intimacao)
    db_session.flush()
    db_session.add_all(
        [
            models.Prazo(
                processo_id=proc.id, intimacao_id=intimacao.id, escritorio_id=esc.id,
                descricao="A",
                data_inicio=date(2024, 9, 9), dias=15, dias_uteis=True,
                data_fatal=date(2024, 9, 30), cumprido=False,
            ),
            models.Prazo(
                processo_id=proc.id, intimacao_id=intimacao.id, escritorio_id=esc.id,
                descricao="B",
                data_inicio=date(2024, 9, 9), dias=5, dias_uteis=True,
                data_fatal=date(2024, 9, 16), cumprido=True,
            ),
        ]
    )
    db_session.flush()
    return proc
