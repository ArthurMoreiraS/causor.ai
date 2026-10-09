"""Delete the dependent records of an explicitly selected OAB or process cleanup.

Object storage and audit events are deliberately retained. These helpers do
not commit: the selected database records disappear atomically.
"""

from sqlalchemy import delete, or_, select

from app.sor import models


def purge_case_dependencies(session, *, process_ids, petition_ids, deadline_ids):
    instance_ids = set(session.scalars(select(models.ProcessoInstancia.id).where(
        models.ProcessoInstancia.processo_id.in_(process_ids))))
    capture_ids = set(session.scalars(select(models.CapturaAutos.id).where(
        models.CapturaAutos.processo_instancia_id.in_(instance_ids))))
    document_ids = set(session.scalars(select(models.Documento.id).where(or_(
        models.Documento.processo_id.in_(process_ids), models.Documento.peticao_id.in_(petition_ids),
        models.Documento.processo_instancia_id.in_(instance_ids)))))
    archive_ids = set(session.scalars(select(models.DocumentoArquivo.id).where(or_(
        models.DocumentoArquivo.documento_id.in_(document_ids), models.DocumentoArquivo.captura_id.in_(capture_ids)))))

    # Bulk DELETE bypasses ORM relationship cascades; child rows must go first.
    session.execute(delete(models.ManifestoItem).where(or_(
        models.ManifestoItem.captura_id.in_(capture_ids), models.ManifestoItem.documento_id.in_(document_ids),
        models.ManifestoItem.documento_arquivo_id.in_(archive_ids))))
    for model in (models.DocumentoResumo, models.DocumentoTrecho):
        session.execute(delete(model).where(model.documento_arquivo_id.in_(archive_ids)))
    session.execute(delete(models.DocumentoArquivo).where(models.DocumentoArquivo.id.in_(archive_ids)))
    documents = session.execute(delete(models.Documento).where(models.Documento.id.in_(document_ids))).rowcount or 0
    session.execute(delete(models.CapturaAutos).where(models.CapturaAutos.id.in_(capture_ids)))
    session.execute(delete(models.ProcessoInstancia).where(models.ProcessoInstancia.id.in_(instance_ids)))
    for model in (models.ContextOverride, models.ContextoProcesso):
        session.execute(delete(model).where(model.processo_id.in_(process_ids)))
    session.execute(delete(models.NotificacaoPrazo).where(models.NotificacaoPrazo.prazo_id.in_(deadline_ids)))
    return documents, {"documento": document_ids, "documento_arquivo": archive_ids,
                       "captura_autos": capture_ids, "processo_instancia": instance_ids}


class ProcessoEmUso(Exception):
    """A worker is running on a record of the process; deleting would race it."""


def purge_process(session, *, escritorio_id, processo_id, descartar_publicacoes=False, recusar_em_execucao=False):
    """Delete a process and everything the office recorded under it.

    Works, their tasks, drafts, deadlines, notices, movements, documents and
    queued jobs go with it. ``descartar_publicacoes`` remembers the notices so
    the capture lookback does not bring the same publications back. Object
    storage and audit events are retained. Does not commit.
    """
    notices = list(session.scalars(select(models.Intimacao).where(
        models.Intimacao.escritorio_id == escritorio_id, models.Intimacao.processo_id == processo_id)))
    notice_ids = {notice.id for notice in notices}
    work_ids = set(session.scalars(select(models.TrabalhoJuridico.id).where(
        models.TrabalhoJuridico.escritorio_id == escritorio_id, models.TrabalhoJuridico.processo_id == processo_id)))
    petition_ids = set(session.scalars(select(models.Peticao.id).where(models.Peticao.processo_id == processo_id)))
    deadline_ids = set(session.scalars(select(models.Prazo.id).where(
        models.Prazo.escritorio_id == escritorio_id,
        or_(models.Prazo.processo_id == processo_id, models.Prazo.intimacao_id.in_(notice_ids)))))
    task_ids = set(session.scalars(select(models.Tarefa.id).where(
        models.Tarefa.escritorio_id == escritorio_id,
        or_(models.Tarefa.processo_id == processo_id, models.Tarefa.trabalho_id.in_(work_ids),
            models.Tarefa.intimacao_id.in_(notice_ids), models.Tarefa.peticao_id.in_(petition_ids)))))

    if descartar_publicacoes:
        known = {(row.fonte, row.fonte_id) for row in session.scalars(select(models.IntimacaoDescartada).where(
            models.IntimacaoDescartada.escritorio_id == escritorio_id))}
        session.add_all(models.IntimacaoDescartada(
            escritorio_id=escritorio_id, fonte=notice.fonte, fonte_id=notice.fonte_id,
            numero_processo=notice.numero_processo) for notice in notices if (notice.fonte, notice.fonte_id) not in known)

    if task_ids:
        session.execute(delete(models.TarefaDocumento).where(models.TarefaDocumento.tarefa_id.in_(task_ids)))
        session.execute(delete(models.Tarefa).where(models.Tarefa.id.in_(task_ids)))
    if work_ids:
        session.execute(delete(models.TrabalhoJuridico).where(models.TrabalhoJuridico.id.in_(work_ids)))
    documents, document_entities = purge_case_dependencies(
        session, process_ids={processo_id}, petition_ids=petition_ids, deadline_ids=deadline_ids)
    session.execute(delete(models.Andamento).where(models.Andamento.processo_id == processo_id))

    # Entity ids come from this office's process, so they identify its jobs.
    entity_ids = {**document_entities, "intimacao": notice_ids, "prazo": deadline_ids, "processo": {processo_id},
                  "trabalho_juridico": work_ids, "peticao": petition_ids, "tarefa": task_ids}
    jobs = [job for job in session.scalars(select(models.JobExecucao).where(
        models.JobExecucao.entidade.in_(list(entity_ids)))) if job.entidade_id in entity_ids[job.entidade]]
    if recusar_em_execucao and any(job.status == "running" for job in jobs):
        raise ProcessoEmUso()
    if jobs:
        session.execute(delete(models.JobExecucao).where(models.JobExecucao.id.in_([job.id for job in jobs])))

    if petition_ids:
        session.execute(delete(models.Peticao).where(models.Peticao.id.in_(petition_ids)))
    if deadline_ids:
        session.execute(delete(models.Prazo).where(models.Prazo.id.in_(deadline_ids)))
    if notice_ids:
        session.execute(delete(models.Intimacao).where(models.Intimacao.id.in_(notice_ids)))
    session.execute(delete(models.Processo).where(models.Processo.id == processo_id))
    return {"trabalhos": len(work_ids), "minutas": len(petition_ids), "tarefas": len(task_ids),
            "prazos": len(deadline_ids), "intimacoes": len(notice_ids), "documentos": documents, "processos": 1}
