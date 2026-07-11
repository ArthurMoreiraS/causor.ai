"""Protocolo real roda no agente local; o backend hospedado nunca abre browser."""

from app.queue.jobs import run_pje_protocol_job
from app.sor import models
from tests.conftest import seed_connected_court_session, seed_filing_ready


def _approved_petition(db_session, *, tribunal="TJMG", sistema="PJe"):
    esc = models.Escritorio(nome="Esc Agent")
    db_session.add(esc)
    db_session.flush()
    usuario = models.Usuario(escritorio_id=esc.id, nome="Adv", email="a@e.com")
    db_session.add(usuario)
    db_session.flush()
    processo = models.Processo(
        escritorio_id=esc.id, numero="0000001-00.2024.8.13.0100",
        tribunal=tribunal, sistema=sistema,
    )
    db_session.add(processo)
    db_session.flush()
    peticao = models.Peticao(
        escritorio_id=esc.id, processo_id=processo.id, tipo="Manifestacao",
        conteudo="minuta", status="aprovada", aprovada_por=usuario.id,
    )
    db_session.add(peticao)
    db_session.flush()
    seed_filing_ready(db_session, peticao)
    return usuario, peticao


def test_real_filing_enqueues_local_agent_without_opening_browser(db_session, monkeypatch):
    usuario, peticao = _approved_petition(db_session)
    seed_connected_court_session(
        db_session, escritorio_id=peticao.escritorio_id, sistema="PJe",
        tribunal="TJMG", grau="1",
    )
    monkeypatch.setattr(
        "app.connectors.pje.session.PjeBrowserSession.__enter__",
        lambda self: (_ for _ in ()).throw(AssertionError("server opened browser")),
    )

    job = run_pje_protocol_job(
        db_session,
        peticao.id,
        usuario_id=usuario.id,
        filing_mode="real",
        submit=False,
    )

    command = db_session.query(models.AgentCommand).filter_by(tipo="prepare_filing").one()
    assert job.status in {"queued", "running"}
    assert command.payload["peticao_id"] == peticao.id
    assert command.payload["submit"] is False
    assert command.payload["pdf_object_key"]
    assert "storage_state" not in command.payload
    # não marca protocolada até o agente confirmar
    db_session.refresh(peticao)
    assert peticao.status == "aprovada"


def test_real_submit_without_connected_session_fails_closed(db_session, monkeypatch):
    usuario, peticao = _approved_petition(db_session)
    monkeypatch.setattr(
        "app.connectors.pje.session.PjeBrowserSession.__enter__",
        lambda self: (_ for _ in ()).throw(AssertionError("server opened browser")),
    )

    job = run_pje_protocol_job(
        db_session,
        peticao.id,
        usuario_id=usuario.id,
        filing_mode="real",
        submit=True,
    )

    assert job.status == "failed"
    assert "conecte" in (job.erro or "").lower()
    assert db_session.query(models.AgentCommand).filter_by(tipo="prepare_filing").count() == 0
    db_session.refresh(peticao)
    assert peticao.status == "aprovada"


def test_sandbox_mode_stays_synchronous(db_session):
    usuario, peticao = _approved_petition(db_session, tribunal="TJSP", sistema="e-SAJ")
    seed_connected_court_session(
        db_session, escritorio_id=peticao.escritorio_id, sistema="e-SAJ",
        tribunal="TJSP", grau="1",
    )

    job = run_pje_protocol_job(
        db_session, peticao.id, usuario_id=usuario.id, submit=True, filing_mode="sandbox"
    )

    assert job.status == "completed"
    assert db_session.query(models.AgentCommand).filter_by(tipo="prepare_filing").count() == 0
