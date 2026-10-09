import pytest
from sqlalchemy import select, text

from app.capture.poll import poll_oab
from app.prazo_engine.factory import build_calendar
from app.sor import models
from tests.test_poll_oab import JANELA, FakeDatajud, FakeDjen, _comunicacao


@pytest.fixture(autouse=True)
def foreign_keys(db_session):
    if db_session.bind.dialect.name == "sqlite":
        db_session.commit()
        db_session.execute(text("PRAGMA foreign_keys=ON"))


def full_case(db_session, seeded):
    """The seeded process with one of every record the office can attach to it."""
    office = seeded.escritorio_id
    notice = db_session.scalars(select(models.Intimacao).where(models.Intimacao.processo_id == seeded.id)).first()
    deadline = db_session.scalars(select(models.Prazo).where(models.Prazo.processo_id == seeded.id)).first()
    draft = models.Peticao(escritorio_id=office, processo_id=seeded.id, prazo_id=deadline.id, status="rascunho")
    instance = models.ProcessoInstancia(escritorio_id=office, processo_id=seeded.id, sistema="PJe", tribunal="TJSP", grau="1")
    db_session.add_all([draft, instance])
    db_session.flush()
    work = models.TrabalhoJuridico(escritorio_id=office, processo_id=seeded.id, intimacao_id=notice.id,
                                   prazo_id=deadline.id, peticao_id=draft.id, providencia="Contestação")
    capture = models.CapturaAutos(escritorio_id=office, processo_instancia_id=instance.id, generation=1, status="complete")
    document = models.Documento(escritorio_id=office, processo_id=seeded.id, processo_instancia_id=instance.id, nome="Autos")
    db_session.add_all([work, capture, document])
    db_session.flush()
    archive = models.DocumentoArquivo(documento_id=document.id, captura_id=capture.id, sha256="a" * 64,
                                      storage_key="test/retained-object", uri="test://file",
                                      mime_type="application/pdf", size_bytes=10)
    task = models.Tarefa(escritorio_id=office, processo_id=seeded.id, trabalho_id=work.id, titulo="Juntar procuração")
    notice_task = models.Tarefa(escritorio_id=office, intimacao_id=notice.id, titulo="Ler intimação")
    db_session.add_all([archive, task, notice_task,
                        models.Andamento(processo_id=seeded.id, codigo=26, descricao="Distribuição"),
                        models.JobExecucao(tipo="minuta_trabalho", status="queued", entidade="trabalho_juridico",
                                           entidade_id=work.id, payload={"escritorio_id": office})])
    db_session.commit()
    return {"notice": notice.id, "draft": draft.id, "work": work.id, "document": document.id,
            "archive": archive.id, "tasks": [task.id, notice_task.id]}


def test_deleting_process_removes_everything_attached(client, db_session, seeded):
    ids = full_case(db_session, seeded)
    customer = models.Cliente(escritorio_id=seeded.escritorio_id, nome="Cliente preservado")
    db_session.add(customer)
    db_session.flush()
    seeded.cliente_id = customer.id
    db_session.commit()
    process_id, customer_id = seeded.id, customer.id

    response = client.delete(f"/processos/{process_id}")

    assert response.status_code == 200, response.text
    assert response.json() == {"processo_id": process_id, "removidos": {
        "trabalhos": 1, "minutas": 1, "tarefas": 2, "prazos": 2, "intimacoes": 1, "documentos": 1, "processos": 1}}
    db_session.expire_all()
    assert db_session.get(models.Processo, process_id) is None
    assert db_session.get(models.Intimacao, ids["notice"]) is None
    assert db_session.get(models.Peticao, ids["draft"]) is None
    assert db_session.get(models.TrabalhoJuridico, ids["work"]) is None
    assert db_session.get(models.Documento, ids["document"]) is None
    assert db_session.get(models.DocumentoArquivo, ids["archive"]) is None
    assert all(db_session.get(models.Tarefa, task_id) is None for task_id in ids["tasks"])
    assert not db_session.scalars(select(models.Prazo).where(models.Prazo.processo_id == process_id)).all()
    assert not db_session.scalars(select(models.Andamento).where(models.Andamento.processo_id == process_id)).all()
    assert not db_session.scalars(select(models.JobExecucao).where(
        models.JobExecucao.entidade == "trabalho_juridico", models.JobExecucao.entidade_id == ids["work"])).all()
    assert db_session.get(models.Cliente, customer_id) is not None
    event = db_session.scalars(select(models.AuditLog).order_by(models.AuditLog.id.desc())).first()
    assert (event.acao, event.entidade_id, event.detalhe["numero"]) == ("processo_excluido", process_id, seeded.numero)
    assert client.get("/processos").json() == []


def test_capture_does_not_recreate_deleted_publication_but_brings_new_one(client, db_session, seeded):
    office = seeded.escritorio_id
    assert client.delete(f"/processos/{seeded.id}").status_code == 200
    calendar = build_calendar([2024, 2025])
    args = dict(oab="12345", uf="SP", escritorio_id=office, datajud=FakeDatajud({}), calendar=calendar, **JANELA)

    repeat = poll_oab(db_session, djen=FakeDjen([_comunicacao("111")]), **args)

    assert repeat.publicacoes_encontradas == 1 and repeat.intimacoes_novas == 0
    assert db_session.scalars(select(models.Processo)).all() == []

    fresh = poll_oab(db_session, djen=FakeDjen([_comunicacao("111"), _comunicacao("222")]), **args)

    assert fresh.intimacoes_novas == 1
    assert [notice.fonte_id for notice in db_session.scalars(select(models.Intimacao))] == ["222"]
    assert len(db_session.scalars(select(models.Processo)).all()) == 1


@pytest.mark.parametrize("status", ["aprovada", "protocolada"])
def test_approved_draft_blocks_process_deletion(client, db_session, seeded, status):
    db_session.add(models.Peticao(escritorio_id=seeded.escritorio_id, processo_id=seeded.id, status=status))
    db_session.commit()

    response = client.delete(f"/processos/{seeded.id}")

    assert response.status_code == 409
    assert db_session.get(models.Processo, seeded.id) is not None


def test_running_operation_blocks_process_deletion(client, db_session, seeded):
    ids = full_case(db_session, seeded)
    db_session.add(models.JobExecucao(tipo="analise_prazo", status="running", entidade="intimacao",
                                      entidade_id=ids["notice"], payload={"escritorio_id": seeded.escritorio_id}))
    db_session.commit()

    response = client.delete(f"/processos/{seeded.id}")

    assert response.status_code == 409
    db_session.expire_all()
    assert db_session.get(models.Processo, seeded.id) is not None
    assert db_session.get(models.TrabalhoJuridico, ids["work"]) is not None
    assert not db_session.scalars(select(models.IntimacaoDescartada)).all()


def test_assistant_cannot_delete_process(client, db_session, seeded):
    db_session.scalars(select(models.Usuario)).first().papel = "assistente"
    db_session.commit()

    response = client.delete(f"/processos/{seeded.id}")

    assert response.status_code == 403
    assert db_session.get(models.Processo, seeded.id) is not None


def test_process_of_other_office_is_not_found(client, db_session, seeded):
    other = models.Escritorio(nome="Outro")
    db_session.add(other)
    db_session.flush()
    foreign = models.Processo(escritorio_id=other.id, numero="00000020020248260100")
    db_session.add(foreign)
    db_session.commit()

    response = client.delete(f"/processos/{foreign.id}")

    assert response.status_code == 404
    assert db_session.get(models.Processo, foreign.id) is not None
