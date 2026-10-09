from sqlalchemy import select

from app.sor import models


def linked_client(db_session, seeded):
    customer = models.Cliente(escritorio_id=seeded.escritorio_id, nome="Cliente de teste")
    db_session.add(customer)
    db_session.flush()
    seeded.cliente_id = customer.id
    task = models.Tarefa(escritorio_id=seeded.escritorio_id, cliente_id=customer.id, titulo="Ligar para o cliente")
    db_session.add(task)
    db_session.commit()
    return customer.id, task.id


def test_deleting_client_keeps_its_processes_and_tasks_unlinked(client, db_session, seeded):
    customer_id, task_id = linked_client(db_session, seeded)

    response = client.delete(f"/clientes/{customer_id}")

    assert response.status_code == 200, response.text
    assert response.json() == {"cliente_id": customer_id, "processos_desvinculados": 1, "tarefas_desvinculadas": 1}
    db_session.expire_all()
    assert db_session.get(models.Cliente, customer_id) is None
    assert db_session.get(models.Processo, seeded.id).cliente_id is None
    assert db_session.get(models.Tarefa, task_id).cliente_id is None
    event = db_session.scalars(select(models.AuditLog).order_by(models.AuditLog.id.desc())).first()
    assert (event.acao, event.entidade_id, event.detalhe["nome"]) == ("cliente_excluido", customer_id, "Cliente de teste")
    assert client.get("/clientes").json()["total"] == 0


def test_client_of_process_with_approved_draft_is_kept(client, db_session, seeded):
    customer_id, _ = linked_client(db_session, seeded)
    db_session.add(models.Peticao(escritorio_id=seeded.escritorio_id, processo_id=seeded.id, status="aprovada"))
    db_session.commit()

    response = client.delete(f"/clientes/{customer_id}")

    assert response.status_code == 409
    db_session.expire_all()
    assert db_session.get(models.Cliente, customer_id) is not None
    assert db_session.get(models.Processo, seeded.id).cliente_id == customer_id


def test_assistant_cannot_delete_client(client, db_session, seeded):
    customer_id, _ = linked_client(db_session, seeded)
    db_session.scalars(select(models.Usuario)).first().papel = "assistente"
    db_session.commit()

    assert client.delete(f"/clientes/{customer_id}").status_code == 403
    assert db_session.get(models.Cliente, customer_id) is not None


def test_client_of_other_office_is_not_found(client, db_session, seeded):
    other = models.Escritorio(nome="Outro")
    db_session.add(other)
    db_session.flush()
    foreign = models.Cliente(escritorio_id=other.id, nome="Alheio")
    db_session.add(foreign)
    db_session.commit()

    assert client.delete(f"/clientes/{foreign.id}").status_code == 404
    assert db_session.get(models.Cliente, foreign.id) is not None
