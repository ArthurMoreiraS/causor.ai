"""TDD: protocolo roteia por sistema e resolve a sessao do cofre sozinho."""

from app.queue.jobs import run_pje_protocol_job
from app.sor import models
from app.vault.service import store_court_session


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
    return u, pet


def test_esaj_petition_protocols_via_sandbox(db_session):
    u, pet = _seed(db_session, tribunal="TJSP", sistema="e-SAJ")
    store_court_session(
        db_session, usuario_id=u.id, sistema="e-SAJ", tribunal="TJSP", grau="1",
        url_base="https://esaj-treino.tjsp.jus.br",
        storage_state={"cookies": [{"name": "x", "value": "secret-cookie"}]},
    )

    job = run_pje_protocol_job(
        db_session, pet.id, usuario_id=u.id, submit=True, filing_mode="sandbox"
    )

    assert job.status == "completed"
    assert job.resultado["sistema"] == "e-SAJ"
    assert job.resultado["protocolo"].startswith("SANDBOX-")
    db_session.refresh(pet)
    assert pet.status == "protocolada"
    assert "secret-cookie" not in str(job.resultado)


def test_missing_session_fails_clearly(db_session):
    u, pet = _seed(db_session, tribunal="TJMG", sistema="PJe")
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
    store_court_session(
        db_session, usuario_id=u.id, sistema="e-SAJ", tribunal="TJSP", grau="1",
        url_base="https://esaj-treino.tjsp.jus.br",
        storage_state={"cookies": [{"name": "x", "value": "secret-cookie"}]},
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
