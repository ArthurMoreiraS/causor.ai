import pytest
from sqlalchemy import select, text

from app.sor import models
from tests.test_oab_cleanup import tracked_case


@pytest.fixture(autouse=True)
def foreign_keys(db_session):
    if db_session.bind.dialect.name == "sqlite":
        db_session.commit()
        db_session.execute(text("PRAGMA foreign_keys=ON"))


def new_work(client, processo_id, **extra):
    response = client.post("/trabalhos", json={"processo_id": processo_id, "providencia": "Apelação", **extra})
    assert response.status_code == 201, response.text
    return response.json()


def delete_work(client, work):
    return client.delete(f"/trabalhos/{work['id']}", params={"versao": work["versao"]})


def audit_actions(db_session):
    return [row.acao for row in db_session.scalars(select(models.AuditLog).order_by(models.AuditLog.id))]


def test_deleting_last_work_removes_process_of_untracked_oab(client, db_session, seeded):
    oab, notice = tracked_case(db_session, seeded)
    process_id, notice_id = seeded.id, notice.id
    db_session.delete(oab)
    db_session.commit()
    work = new_work(client, process_id, intimacao_id=notice_id)

    response = delete_work(client, work)

    assert response.status_code == 200, response.text
    assert response.json() == {"trabalho_id": work["id"], "minuta_excluida": False,
                               "tarefas_excluidas": 0, "processo_removido": True}
    db_session.expire_all()
    assert db_session.get(models.TrabalhoJuridico, work["id"]) is None
    assert db_session.get(models.Processo, process_id) is None
    assert db_session.get(models.Intimacao, notice_id) is None
    assert not db_session.scalars(select(models.Prazo).where(models.Prazo.processo_id == process_id)).all()
    assert audit_actions(db_session)[-2:] == ["trabalho_excluido", "processo_removido_sem_monitoramento"]
    assert client.get(f"/trabalhos/{work['id']}").status_code == 404


def test_deleting_work_keeps_process_while_oab_is_tracked(client, db_session, seeded):
    tracked_case(db_session, seeded)
    work = new_work(client, seeded.id)

    response = delete_work(client, work)

    assert response.status_code == 200, response.text
    assert response.json()["processo_removido"] is False
    db_session.expire_all()
    assert db_session.get(models.TrabalhoJuridico, work["id"]) is None
    assert db_session.get(models.Processo, seeded.id) is not None


def test_deleting_work_keeps_manual_process(client, db_session, seeded):
    created = client.post("/processos", json={"numero": "0709876-89.2025.8.07.0001", "tribunal": "TJDFT"})
    assert created.status_code == 201, created.text
    work = new_work(client, created.json()["id"])

    response = delete_work(client, work)

    assert response.status_code == 200, response.text
    assert response.json()["processo_removido"] is False
    assert db_session.get(models.Processo, created.json()["id"]) is not None


@pytest.mark.parametrize("kind", ["other_work", "document", "task", "confirmed"])
def test_untracked_process_with_other_authored_records_is_kept(client, db_session, seeded, kind):
    oab, notice = tracked_case(db_session, seeded)
    db_session.delete(oab)
    office = seeded.escritorio_id
    if kind == "other_work":
        db_session.add(models.TrabalhoJuridico(escritorio_id=office, processo_id=seeded.id, providencia="Outro"))
    elif kind == "document":
        db_session.add(models.Documento(escritorio_id=office, processo_id=seeded.id, nome="Autos enviados"))
    elif kind == "task":
        db_session.add(models.Tarefa(escritorio_id=office, processo_id=seeded.id, titulo="Ligar para o cliente"))
    else:
        notice.payload = {**notice.payload, "_causor_prazo": {"status": "confirmado"}}
    db_session.commit()
    work = new_work(client, seeded.id)

    response = delete_work(client, work)

    assert response.status_code == 200, response.text
    assert response.json()["processo_removido"] is False
    assert db_session.get(models.Processo, seeded.id) is not None
    assert db_session.get(models.Intimacao, notice.id) is not None


def test_deleting_work_removes_its_draft_and_gap_tasks(client, db_session, seeded):
    tracked_case(db_session, seeded)
    work = new_work(client, seeded.id)
    office = seeded.escritorio_id
    draft = models.Peticao(escritorio_id=office, processo_id=seeded.id, status="rascunho", conteudo="Minuta")
    db_session.add(draft)
    db_session.flush()
    stored = db_session.get(models.TrabalhoJuridico, work["id"])
    stored.peticao_id = draft.id
    task = models.Tarefa(escritorio_id=office, processo_id=seeded.id, trabalho_id=work["id"],
                         titulo="Juntar sentença", origem="lacuna_trabalho")
    unrelated = models.Tarefa(escritorio_id=office, processo_id=seeded.id, titulo="Tarefa avulsa")
    db_session.add_all([task, unrelated])
    db_session.commit()
    draft_id, task_id, unrelated_id = draft.id, task.id, unrelated.id

    response = delete_work(client, work)

    assert response.status_code == 200, response.text
    assert response.json()["minuta_excluida"] is True
    assert response.json()["tarefas_excluidas"] == 1
    db_session.expire_all()
    assert db_session.get(models.Peticao, draft_id) is None
    assert db_session.get(models.Tarefa, task_id) is None
    assert db_session.get(models.Tarefa, unrelated_id) is not None


@pytest.mark.parametrize("status", ["aprovada", "protocolada"])
def test_approved_draft_blocks_deletion(client, db_session, seeded, status):
    work = new_work(client, seeded.id)
    draft = models.Peticao(escritorio_id=seeded.escritorio_id, processo_id=seeded.id, status=status)
    db_session.add(draft)
    db_session.flush()
    db_session.get(models.TrabalhoJuridico, work["id"]).peticao_id = draft.id
    db_session.commit()

    response = delete_work(client, work)

    assert response.status_code == 409
    assert db_session.get(models.TrabalhoJuridico, work["id"]) is not None


def test_running_operation_blocks_deletion(client, db_session, seeded):
    work = new_work(client, seeded.id)
    db_session.add(models.JobExecucao(tipo="minuta_trabalho", status="running", entidade="trabalho_juridico",
                                      entidade_id=work["id"], payload={"escritorio_id": seeded.escritorio_id}))
    db_session.commit()

    response = delete_work(client, work)

    assert response.status_code == 409
    assert db_session.get(models.TrabalhoJuridico, work["id"]) is not None


def test_stale_version_blocks_deletion(client, db_session, seeded):
    work = new_work(client, seeded.id)

    response = client.delete(f"/trabalhos/{work['id']}", params={"versao": work["versao"] + 1})

    assert response.status_code == 409
    assert db_session.get(models.TrabalhoJuridico, work["id"]) is not None


def test_assistant_cannot_delete_work(client, db_session, seeded):
    work = new_work(client, seeded.id)
    db_session.scalars(select(models.Usuario)).first().papel = "assistente"
    db_session.commit()

    response = delete_work(client, work)

    assert response.status_code == 403
    assert db_session.get(models.TrabalhoJuridico, work["id"]) is not None


def test_work_of_other_office_is_not_found(client, db_session, seeded):
    other = models.Escritorio(nome="Outro")
    db_session.add(other)
    db_session.flush()
    process = models.Processo(escritorio_id=other.id, numero="00000020020248260100")
    db_session.add(process)
    db_session.flush()
    foreign = models.TrabalhoJuridico(escritorio_id=other.id, processo_id=process.id, providencia="Alheio")
    db_session.add(foreign)
    db_session.commit()

    response = client.delete(f"/trabalhos/{foreign.id}", params={"versao": 1})

    assert response.status_code == 404
    assert db_session.get(models.TrabalhoJuridico, foreign.id) is not None
