"""Login de tribunal via UI → comando ao agente → estado derivado.

O advogado dispara o login pelo Causor; o agente abre o portal na máquina
dele e reporta apenas ``session_ready``. Nenhum cookie chega ao backend.
"""

from app.sor import models


def _pair_agent(client) -> dict:
    code = client.post("/agent/pairing-codes").json()["code"]
    paired = client.post(
        "/agent/pair",
        json={"code": code, "installation_name": "Notebook jurídico", "version": "0.1.0"},
    )
    return {"Authorization": f"Agent {paired.json()['token']}"}


def test_login_endpoint_enqueues_command_and_reports_connecting(client, db_session, seeded):
    headers = _pair_agent(client)

    resp = client.post(f"/processos/{seeded.id}/tribunal/login", json={"grau": "1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "conectando"
    assert body["sistema"]
    assert body["tribunal"] == seeded.tribunal

    command = db_session.query(models.AgentCommand).filter_by(tipo="open_court_login").one()
    assert "storage_state" not in command.payload
    assert command.payload["grau"] == "1"

    # agente conclui o login; estado vira conectado sem cookie no backend
    claimed = client.post("/agent/commands/claim", headers=headers).json()
    assert claimed["tipo"] == "open_court_login"
    completed = client.post(
        f"/agent/commands/{claimed['id']}/complete",
        headers=headers,
        json={
            "resultado": {
                "session_ready": True,
                "version_marker": "esaj-1.x",
                "evidence": {"marker": "painel"},
            }
        },
    )
    assert completed.status_code == 200

    sessao = client.get(f"/processos/{seeded.id}/tribunal/sessao").json()
    rota = next(item for item in sessao["rotas"] if item["grau"] == "1")
    assert rota["status"] == "conectado"
    assert "storage_state" not in str(sessao)


def test_failed_login_command_surfaces_error_state(client, db_session, seeded):
    headers = _pair_agent(client)
    client.post(f"/processos/{seeded.id}/tribunal/login", json={"grau": "1"})
    claimed = client.post("/agent/commands/claim", headers=headers).json()
    failed = client.post(
        f"/agent/commands/{claimed['id']}/fail",
        headers=headers,
        json={"erro_codigo": "captcha_required", "erro_detalhe": "desafio no portal"},
    )
    assert failed.status_code == 200

    sessao = client.get(f"/processos/{seeded.id}/tribunal/sessao").json()
    rota = next(item for item in sessao["rotas"] if item["grau"] == "1")
    assert rota["status"] == "desconectado"
    assert rota["last_error_code"] == "captcha_required"


def test_login_endpoint_404_for_other_tenant_process(client, db_session, seeded):
    other = models.Escritorio(nome="Outro Escritório")
    db_session.add(other)
    db_session.flush()
    foreign = models.Processo(
        escritorio_id=other.id, numero="99999999920268260000", tribunal="TJSP"
    )
    db_session.add(foreign)
    db_session.flush()

    resp = client.post(f"/processos/{foreign.id}/tribunal/login", json={"grau": "1"})
    assert resp.status_code == 404
