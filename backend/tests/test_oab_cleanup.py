from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text

from app.sor import models


@pytest.fixture(autouse=True)
def enforce_foreign_keys(db_session):
    if db_session.bind.dialect.name == "sqlite":
        db_session.commit()
        db_session.execute(text("PRAGMA foreign_keys=ON"))


def tracked_case(db_session, seeded):
    oab = models.OabMonitorada(escritorio_id=seeded.escritorio_id, oab="12345", uf="SP")
    notice = db_session.scalars(select(models.Intimacao).where(models.Intimacao.processo_id == seeded.id)).first()
    notice.payload = {"destinatarioadvogados": [{"advogado": {"numero_oab": "12345", "uf_oab": "SP"}}]}
    db_session.add(oab)
    db_session.commit()
    return oab, notice


def test_remove_oab_with_complete_document_graph(client, db_session, seeded):
    oab, notice = tracked_case(db_session, seeded)
    office = seeded.escritorio_id
    user = db_session.scalars(select(models.Usuario)).first()
    deadline = db_session.scalars(select(models.Prazo).where(models.Prazo.processo_id == seeded.id)).first()
    customer = models.Cliente(escritorio_id=office, nome="Cliente preservado")
    instance = models.ProcessoInstancia(escritorio_id=office, processo_id=seeded.id, sistema="PJe", tribunal="TJSP", grau="1")
    draft = models.Peticao(escritorio_id=office, processo_id=seeded.id, prazo_id=deadline.id)
    db_session.add_all([customer, instance, draft])
    db_session.flush()
    seeded.cliente_id = customer.id
    capture = models.CapturaAutos(escritorio_id=office, processo_instancia_id=instance.id, generation=1, status="complete")
    document = models.Documento(escritorio_id=office, processo_id=seeded.id, processo_instancia_id=instance.id, nome="Autos")
    db_session.add_all([capture, document])
    db_session.flush()
    archive = models.DocumentoArquivo(documento_id=document.id, captura_id=capture.id, sha256="a" * 64,
        storage_key="test/retained-object", uri="test://file", mime_type="application/pdf", size_bytes=10)
    db_session.add(archive)
    db_session.flush()
    task = models.Tarefa(escritorio_id=office, titulo="Conferir", processo_id=seeded.id,
        peticao_id=draft.id, intimacao_id=notice.id, origem_texto="Documento pendente")
    db_session.add_all([
        task,
        models.ManifestoItem(captura_id=capture.id, documento_id=document.id, documento_arquivo_id=archive.id, external_id="doc", ordem=1),
        models.DocumentoTrecho(documento_arquivo_id=archive.id, pagina=1, indice=0, texto="Teste", texto_sha256="b" * 64, char_count=5),
        models.DocumentoResumo(documento_arquivo_id=archive.id, resumo="Resumo"),
        models.ContextoProcesso(escritorio_id=office, processo_id=seeded.id, source_fingerprint="c" * 64, inventario=[], cobertura={}),
        models.ContextOverride(escritorio_id=office, processo_id=seeded.id, usuario_id=user.id,
            action="draft", justification="Teste", expires_at=datetime.now(timezone.utc)),
        models.NotificacaoPrazo(escritorio_id=office, prazo_id=deadline.id, nivel="D-1", destino="test@example.invalid"),
        models.AuditLog(escritorio_id=office, ator="teste", acao="evento_preservado", entidade="processo", entidade_id=seeded.id),
        models.JobExecucao(tipo="process_document", entidade="documento_arquivo", entidade_id=archive.id,
            payload={"escritorio_id": office}),
    ])
    db_session.commit()
    ids = oab.id, seeded.id, customer.id, task.id
    response = client.delete(f"/capturas/oab/{oab.id}?purge=true")
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.get(models.OabMonitorada, ids[0]) is None
    assert db_session.get(models.Processo, ids[1]) is None
    assert db_session.get(models.Cliente, ids[2]) is not None
    retained = db_session.get(models.Tarefa, ids[3])
    assert retained.processo_id is None and retained.peticao_id is None and retained.intimacao_id is None
    assert retained.origem_texto == "Documento pendente"
    assert db_session.scalars(select(models.AuditLog).where(models.AuditLog.acao == "evento_preservado")).one()
    for model in (models.Documento, models.DocumentoArquivo, models.ManifestoItem, models.DocumentoTrecho,
                  models.DocumentoResumo, models.CapturaAutos, models.ProcessoInstancia, models.ContextoProcesso,
                  models.ContextOverride, models.NotificacaoPrazo, models.JobExecucao):
        assert db_session.scalars(select(model)).first() is None, model.__name__


@pytest.mark.parametrize("with_notice", [True, False])
def test_oab_cleanup_jobs_are_scoped_to_office(client, db_session, seeded, with_notice):
    oab, notice = tracked_case(db_session, seeded)
    if not with_notice:
        notice.payload = {}
    other_office = models.Escritorio(nome="Outro escritório")
    db_session.add(other_office)
    db_session.flush()
    own = models.JobExecucao(tipo="captura_oab", payload={"oab": oab.oab, "uf": "SP", "escritorio_id": seeded.escritorio_id})
    other = models.JobExecucao(tipo="captura_oab", payload={"oab": oab.oab, "uf": "SP", "escritorio_id": other_office.id})
    db_session.add_all([own, other])
    db_session.commit()
    assert client.delete(f"/capturas/oab/{oab.id}?purge=true").status_code == 200
    assert db_session.get(models.JobExecucao, own.id) is None
    assert db_session.get(models.JobExecucao, other.id) is not None


def test_stop_tracking_without_purge_preserves_case(client, db_session, seeded):
    oab, notice = tracked_case(db_session, seeded)
    assert client.delete(f"/capturas/oab/{oab.id}?purge=false").status_code == 200
    assert db_session.get(models.Intimacao, notice.id) is not None
    assert db_session.get(models.Processo, seeded.id) is not None


def test_shared_process_and_its_documents_survive_other_oab_removal(client, db_session, seeded):
    oab, notice = tracked_case(db_session, seeded)
    other_notice = models.Intimacao(escritorio_id=seeded.escritorio_id, processo_id=seeded.id,
        fonte="DJEN", fonte_id="other-registration", payload={"destinatarioadvogados": [
            {"advogado": {"numero_oab": "99999", "uf_oab": "SP"}}]})
    document = models.Documento(escritorio_id=seeded.escritorio_id, processo_id=seeded.id, nome="Autos compartilhados")
    context = models.ContextoProcesso(escritorio_id=seeded.escritorio_id, processo_id=seeded.id,
        source_fingerprint="c" * 64, inventario=[], cobertura={})
    db_session.add_all([other_notice, document, context])
    db_session.commit()
    response = client.delete(f"/capturas/oab/{oab.id}?purge=true")
    assert response.status_code == 200, response.text
    assert response.json()["removidos"]["processos"] == 0
    assert db_session.get(models.Intimacao, notice.id) is None
    assert db_session.get(models.Intimacao, other_notice.id) is not None
    assert db_session.get(models.Processo, seeded.id) is not None
    assert db_session.get(models.Documento, document.id) is not None
    assert db_session.get(models.ContextoProcesso, context.id) is not None


def test_cannot_remove_another_offices_tracked_oab(client, db_session, seeded):
    other = models.Escritorio(nome="Privado")
    db_session.add(other)
    db_session.flush()
    registration = models.OabMonitorada(escritorio_id=other.id, oab="12345", uf="SP")
    db_session.add(registration)
    db_session.commit()
    assert client.delete(f"/capturas/oab/{registration.id}?purge=true").status_code == 404
    assert db_session.get(models.OabMonitorada, registration.id) is not None
