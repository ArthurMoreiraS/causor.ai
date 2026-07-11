"""Protocolo roteia por sistema e exige sessão conectada no agente local."""

from app.queue.jobs import run_pje_protocol_job
from app.sor import models
from tests.conftest import seed_connected_court_session, seed_filing_ready


def _seed(db_session, *, tribunal, sistema):
    esc = models.Escritorio(nome="Esc")
    db_session.add(esc)
    db_session.flush()
    u = models.Usuario(escritorio_id=esc.id, nome="Adv", email="a@e.com")
    db_session.add(u)
    db_session.flush()
    proc = models.Processo(
        escritorio_id=esc.id, numero="0000001-00.2024.8.26.0100",
        tribunal=tribunal, sistema=sistema,
    )
    db_session.add(proc)
    db_session.flush()
    pet = models.Peticao(
        escritorio_id=esc.id, processo_id=proc.id, tipo="Manifestacao",
        conteudo="minuta", status="aprovada", aprovada_por=u.id,
    )
    db_session.add(pet)
    db_session.flush()
    seed_filing_ready(db_session, pet)
    return u, pet


def test_esaj_petition_protocols_via_sandbox(db_session):
    u, pet = _seed(db_session, tribunal="TJSP", sistema="e-SAJ")
    seed_connected_court_session(
        db_session, escritorio_id=pet.escritorio_id, sistema="e-SAJ",
        tribunal="TJSP", grau="1",
    )

    job = run_pje_protocol_job(
        db_session, pet.id, usuario_id=u.id, submit=True, filing_mode="sandbox"
    )

    assert job.status == "completed"
    assert job.resultado["sistema"] == "e-SAJ"
    assert job.resultado["protocolo"].startswith("SANDBOX-")
    db_session.refresh(pet)
    assert pet.status == "protocolada"
    assert "storage_state" not in str(job.payload)
    assert "storage_state" not in str(job.resultado)


def test_missing_session_fails_clearly(db_session):
    u, pet = _seed(db_session, tribunal="TJMG", sistema="PJe")
    job = run_pje_protocol_job(
        db_session, pet.id, usuario_id=u.id, submit=True, filing_mode="sandbox"
    )
    assert job.status == "failed"
    assert "conecte" in (job.erro or "").lower()


def test_expired_session_fails_clearly(db_session):
    u, pet = _seed(db_session, tribunal="TJMG", sistema="PJe")
    state = seed_connected_court_session(
        db_session, escritorio_id=pet.escritorio_id, sistema="PJe",
        tribunal="TJMG", grau="1",
    )
    state.status = "expirado"
    db_session.flush()

    job = run_pje_protocol_job(
        db_session, pet.id, usuario_id=u.id, submit=True, filing_mode="sandbox"
    )
    assert job.status == "failed"
    assert "conecte" in (job.erro or "").lower()


def test_protocolo_renderiza_pdf_com_timbrado_do_escritorio(db_session, monkeypatch):
    u, pet = _seed(db_session, tribunal="TJSP", sistema="e-SAJ")
    esc = db_session.get(models.Escritorio, pet.escritorio_id)
    esc.timbrado_rodape = "OAB/SP 123.456"
    db_session.flush()
    seed_connected_court_session(
        db_session, escritorio_id=pet.escritorio_id, sistema="e-SAJ",
        tribunal="TJSP", grau="1",
    )

    import app.queue.jobs as jobs_mod

    original = jobs_mod.render_minuta_pdf
    capturado = {}

    def espiao(texto, *, meta=None, timbrado=None):
        capturado["timbrado"] = timbrado
        return original(texto, meta=meta, timbrado=timbrado)

    monkeypatch.setattr(jobs_mod, "render_minuta_pdf", espiao)

    job = run_pje_protocol_job(
        db_session, pet.id, usuario_id=u.id, submit=True, filing_mode="sandbox"
    )

    assert job.status == "completed"
    assert capturado["timbrado"] is not None
    assert capturado["timbrado"].rodape == "OAB/SP 123.456"
