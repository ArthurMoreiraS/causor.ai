from datetime import date

import pytest

from app.agent.service import draft_from_intimacao
from app.autos.context import (
    ContextNotReadyError,
    create_context_override,
    consume_context_override,
    require_ready_context,
)
from app.prazo_engine.factory import build_calendar
from app.sor import models
from tests.conftest import seed_ready_context


@pytest.fixture
def calendar():
    return build_calendar([2024, 2025, 2026])


@pytest.fixture
def seeded_intimacao(db_session, seeded):
    return (
        db_session.query(models.Intimacao).filter_by(processo_id=seeded.id).first()
    )


@pytest.fixture
def current_user(db_session, seeded):
    usuario = db_session.query(models.Usuario).first()

    class _User:
        usuario_id = usuario.id
        escritorio_id = usuario.escritorio_id

    return _User()


def test_draft_is_blocked_without_ready_context(db_session, seeded_intimacao, calendar):
    with pytest.raises(ContextNotReadyError) as exc:
        draft_from_intimacao(db_session, seeded_intimacao, calendar=calendar)
    assert exc.value.code == "process_context_incomplete"


def test_lawyer_override_is_consumed_once(db_session, seeded, current_user):
    override = create_context_override(
        db_session,
        processo=seeded,
        usuario_id=current_user.usuario_id,
        action="draft",
        justification="Prazo fatal hoje; autos conferidos manualmente pelo advogado.",
    )
    assert (
        consume_context_override(
            db_session, processo=seeded, usuario_id=current_user.usuario_id, action="draft"
        ).id
        == override.id
    )
    assert (
        consume_context_override(
            db_session, processo=seeded, usuario_id=current_user.usuario_id, action="draft"
        )
        is None
    )


def test_override_requires_meaningful_justification(db_session, seeded, current_user):
    with pytest.raises(ValueError):
        create_context_override(
            db_session,
            processo=seeded,
            usuario_id=current_user.usuario_id,
            action="draft",
            justification="curta",
        )


def test_gate_passes_with_seeded_ready_context(db_session, seeded, current_user):
    seed_ready_context(db_session, seeded)
    assert (
        require_ready_context(
            db_session, processo=seeded, usuario_id=current_user.usuario_id, action="draft"
        )
        == "ready"
    )


def test_gate_accepts_override_when_incomplete(db_session, seeded, current_user):
    create_context_override(
        db_session,
        processo=seeded,
        usuario_id=current_user.usuario_id,
        action="draft",
        justification="Prazo fatal hoje; autos conferidos manualmente pelo advogado.",
    )
    assert (
        require_ready_context(
            db_session, processo=seeded, usuario_id=current_user.usuario_id, action="draft"
        )
        == "override"
    )
    audit = (
        db_session.query(models.AuditLog)
        .filter_by(acao="process_context_override_consumed")
        .count()
    )
    assert audit == 1


def test_override_endpoint_creates_and_audits(client, db_session, seeded):
    response = client.post(
        f"/processos/{seeded.id}/contexto/override",
        json={
            "action": "draft",
            "justification": "Prazo fatal hoje; autos conferidos manualmente pelo advogado.",
        },
    )
    assert response.status_code == 200
    assert (
        db_session.query(models.AuditLog)
        .filter_by(acao="process_context_override_created")
        .count()
        == 1
    )


def test_intimacao_without_processo_is_blocked(db_session, seeded, calendar):
    intimacao = models.Intimacao(
        processo_id=None,
        escritorio_id=seeded.escritorio_id,
        fonte="DJEN",
        fonte_id="999",
        numero_processo=None,
        tipo_comunicacao="Intimação",
        data_disponibilizacao=date(2024, 9, 6),
        teor="Teor sem processo vinculado.",
    )
    db_session.add(intimacao)
    db_session.flush()
    with pytest.raises(ContextNotReadyError):
        draft_from_intimacao(db_session, intimacao, calendar=calendar)
