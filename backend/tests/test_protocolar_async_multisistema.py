"""O protocolo async roteia qualquer sistema (e-SAJ, etc.) via driver."""

from app.sor import models
from app.vault.service import store_court_session
from tests.conftest import seed_filing_ready


def _peticao_aprovada(db_session, seeded):
    usuario = db_session.query(models.Usuario).first()
    peticao = models.Peticao(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
        tipo="Manifestacao",
        conteudo="minuta",
        status="aprovada",
        aprovada_por=usuario.id,
    )
    db_session.add(peticao)
    db_session.flush()
    seed_filing_ready(db_session, peticao)
    return usuario, peticao


def test_esaj_petition_protocols_via_async_in_sandbox(client, db_session, seeded):
    # seeded é TJSP -> registro resolve e-SAJ. Conecta a sessao no cofre.
    seeded.sistema = "e-SAJ"
    usuario, peticao = _peticao_aprovada(db_session, seeded)
    store_court_session(
        db_session, usuario_id=usuario.id, sistema="e-SAJ", tribunal="TJSP", grau="1",
        url_base="https://esaj-treino.tjsp.jus.br",
        storage_state={"cookies": [{"name": "x", "value": "s"}]},
    )

    resp = client.post(f"/peticoes/{peticao.id}/protocolar/async", json={})

    assert resp.status_code == 200
    job = resp.json()
    assert job["status"] == "completed"
    assert job["resultado"]["sistema"] == "e-SAJ"
    assert job["resultado"]["protocolo"].startswith("SANDBOX-")


def test_esaj_sem_sessao_retorna_job_falho(client, db_session, seeded):
    seeded.sistema = "e-SAJ"
    _usuario, peticao = _peticao_aprovada(db_session, seeded)

    resp = client.post(f"/peticoes/{peticao.id}/protocolar/async", json={})

    assert resp.status_code == 200
    job = resp.json()
    assert job["status"] == "failed"
    assert "conecte" in (job["erro"] or "").lower()
