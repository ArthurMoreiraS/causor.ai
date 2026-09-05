import pytest

from app.sor import models


def test_client_registration_and_process_link(client, db_session, seeded):
    result = client.post("/clientes", json={"nome": "Cliente do escritório", "documento": "123"})
    assert result.status_code == 201
    customer_id = result.json()["id"]
    linked = client.put(f"/processos/{seeded.id}/cliente", json={"cliente_id": customer_id})
    assert linked.status_code == 200
    db_session.refresh(seeded)
    assert seeded.cliente_id == customer_id
    listing = client.get("/clientes", params={"q": "Cliente do escritório"}).json()
    assert listing["total"] == 1
    assert listing["items"][0]["processos_count"] == 1
    assert client.get("/processos").json()[0]["cliente_id"] == customer_id


def test_notice_becomes_task_without_creating_a_legal_deadline(client, db_session, seeded):
    notice = db_session.query(models.Intimacao).first()
    before = db_session.query(models.Prazo).count()
    response = client.post("/tarefas", json={"titulo": "Solicitar comprovante", "tipo": "documento",
                          "intimacao_id": notice.id, "data_prevista": "2026-10-02"})
    assert response.status_code == 201
    task = response.json()
    assert task["processo_id"] == seeded.id and task["intimacao_id"] == notice.id
    assert task["processo_numero"] == seeded.numero
    assert task["data_prevista"] == "2026-10-02" and task["status"] == "aberta"
    assert db_session.query(models.Prazo).count() == before
    done = client.patch(f"/tarefas/{task['id']}", json={"versao": task["versao"], "status": "concluida"})
    assert done.status_code == 200 and done.json()["concluida_em"]
    assert client.patch(f"/tarefas/{task['id']}", json={"versao": task["versao"], "status": "aberta"}).status_code == 409
    assert db_session.query(models.AuditLog).filter_by(acao="tarefa_atualizada").count() == 1


@pytest.mark.parametrize("field,kind", [("processo_id", "process"), ("cliente_id", "customer"),
                                       ("responsavel_id", "user"), ("intimacao_id", "notice"), ("peticao_id", "draft")])
def test_task_cannot_reference_other_office(client, db_session, seeded, field, kind):
    office = models.Escritorio(nome="Outro escritório")
    db_session.add(office)
    db_session.flush()
    process = models.Processo(escritorio_id=office.id, numero="outro-processo")
    customer = models.Cliente(escritorio_id=office.id, nome="Cliente privado")
    user = models.Usuario(escritorio_id=office.id, nome="Outro usuário", email="outro@example.invalid")
    db_session.add_all([process, customer, user])
    db_session.flush()
    notice = models.Intimacao(escritorio_id=office.id, processo_id=process.id, fonte="teste", fonte_id="outro")
    draft = models.Peticao(escritorio_id=office.id, processo_id=process.id, dossie={"alertas": ["Lacuna"]})
    db_session.add_all([notice, draft])
    db_session.commit()
    selected = {"process": process, "customer": customer, "user": user, "notice": notice, "draft": draft}[kind]
    payload = {"titulo": "Conferir", field: selected.id}
    if kind == "draft":
        payload["alerta_indice"] = 0
        payload["alerta_texto_esperado"] = "Lacuna"
    assert client.post("/tarefas", json=payload).status_code == 404
    assert client.put(f"/processos/{seeded.id}/cliente", json={"cliente_id": customer.id}).status_code == 404
    assert "Cliente privado" not in client.get("/clientes").text


def test_ai_alert_has_verified_origin_and_is_not_duplicated(client, db_session, seeded):
    draft = models.Peticao(escritorio_id=seeded.escritorio_id, processo_id=seeded.id,
                           dossie={"alertas": ["Falta o comprovante de pagamento."]})
    db_session.add(draft)
    db_session.commit()
    payload = {"titulo": "Obter comprovante", "tipo": "documento", "peticao_id": draft.id, "alerta_indice": 0,
               "alerta_texto_esperado": "Falta o comprovante de pagamento."}
    first = client.post("/tarefas", json=payload)
    second = client.post("/tarefas", json=payload)
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["origem_texto"] == "Falta o comprovante de pagamento."
    assert first.json()["origem"] == "alerta_minuta"
    opened = client.get(f"/peticoes/{draft.id}")
    assert opened.status_code == 200 and opened.json()["dossie"]["alertas"] == draft.dossie["alertas"]
    assert client.post("/tarefas", json={**payload, "alerta_indice": 9}).status_code == 422
    assert client.post("/tarefas", json={**payload, "alerta_texto_esperado": "Outro alerta"}).status_code == 409
    assert client.get("/tarefas", params={"processo_id": seeded.id}).json()["total"] == 1


def test_task_listing_paginates_and_does_not_expose_other_office(client, db_session, seeded):
    for title in ("Revisar autos", "Revisar minuta", "Solicitar contrato"):
        assert client.post("/tarefas", json={"titulo": title}).status_code == 201
    office = models.Escritorio(nome="Outro")
    db_session.add(office)
    db_session.flush()
    db_session.add(models.Tarefa(escritorio_id=office.id, titulo="Segredo", tipo="providencia"))
    db_session.commit()
    result = client.get("/tarefas", params={"q": "Revisar", "limit": 1, "offset": 1}).json()
    assert result["total"] == 2 and len(result["items"]) == 1
    assert "Segredo" not in client.get("/tarefas").text


def test_changing_client_is_blocked_while_a_draft_is_approved(client, db_session, seeded):
    db_session.add(models.Peticao(escritorio_id=seeded.escritorio_id, processo_id=seeded.id, status="aprovada"))
    customer = models.Cliente(escritorio_id=seeded.escritorio_id, nome="Novo")
    db_session.add(customer)
    db_session.commit()
    assert client.put(f"/processos/{seeded.id}/cliente", json={"cliente_id": customer.id}).status_code == 409


def test_task_reopening_and_reassignment_preserve_source(client, db_session, seeded):
    notice = db_session.query(models.Intimacao).first()
    task = client.post("/tarefas", json={"titulo": "Conferir", "intimacao_id": notice.id,
                                       "data_prevista": "2026-10-02"}).json()
    done = client.patch(f"/tarefas/{task['id']}", json={"versao": 1, "status": "concluida"}).json()
    reopened = client.patch(f"/tarefas/{task['id']}", json={"versao": done["versao"],
                            "status": "em_andamento", "data_prevista": None}).json()
    assert reopened["concluida_em"] is None and reopened["data_prevista"] is None
    assert reopened["intimacao_id"] == notice.id and reopened["versao"] == 3
    for patch in ({"status": "invalido"}, {"titulo": None}, {"processo_id": None}):
        assert client.patch(f"/tarefas/{task['id']}", json={"versao": 3, **patch}).status_code == 422
    office = models.Escritorio(nome="Outro")
    db_session.add(office)
    db_session.flush()
    user = models.Usuario(escritorio_id=office.id, nome="Privado", email="privado@example.invalid")
    private_task = models.Tarefa(escritorio_id=office.id, titulo="Privada")
    process = models.Processo(escritorio_id=office.id, numero="privado")
    db_session.add_all([user, private_task, process])
    db_session.flush()
    draft = models.Peticao(escritorio_id=office.id, processo_id=process.id)
    db_session.add(draft)
    db_session.commit()
    assert client.patch(f"/tarefas/{task['id']}", json={"versao": 3, "responsavel_id": user.id}).status_code == 404
    assert client.patch(f"/tarefas/{private_task.id}", json={"versao": 1, "status": "concluida"}).status_code == 404
    assert client.get(f"/peticoes/{draft.id}").status_code == 404


def test_task_client_follows_process_and_rejects_mismatched_sources(client, db_session, seeded):
    customer = client.post("/clientes", json={"nome": "Representado"}).json()
    task = client.post("/tarefas", json={"titulo": "Conferir autos", "processo_id": seeded.id}).json()
    assert client.put(f"/processos/{seeded.id}/cliente", json={"cliente_id": customer["id"]}).status_code == 200
    listing = client.get("/tarefas", params={"cliente_id": customer["id"]}).json()
    assert listing["items"][0]["id"] == task["id"]
    assert listing["items"][0]["cliente_nome"] == "Representado"
    other = models.Processo(escritorio_id=seeded.escritorio_id, numero="outro-mesmo-escritorio")
    db_session.add(other)
    db_session.commit()
    notice = db_session.query(models.Intimacao).first()
    assert client.post("/tarefas", json={"titulo": "Inválida", "processo_id": other.id,
                                       "intimacao_id": notice.id}).status_code == 422
    assert client.post("/tarefas", json={"titulo": "Inválida", "processo_id": other.id,
                                       "cliente_id": customer["id"]}).status_code == 422
