"""Delete the dependent records of an explicitly selected OAB cleanup.

Object storage and audit events are deliberately retained. This helper does
not commit: the OAB and all selected database records disappear atomically.
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
