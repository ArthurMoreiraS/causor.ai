"""Tenant-scoped document inventory, immutable versions and cited page text."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.autos_routes import _get_owned_documento
from app.auth.jwt_auth import CurrentUser, get_current_user
from app.auth.tenant import get_owned_or_404
from app.sor import models as m
from app.sor.db import get_session

router = APIRouter(tags=["documentos"])


def version_out(version, summary=None):
    return {"id": version.id, "sha256": version.sha256, "mime_type": version.mime_type,
        "size_bytes": version.size_bytes, "paginas": version.page_count, "atual": version.atual,
        "extracao": version.extraction_status, "resumo_status": summary.status if summary else "pending",
        "created_at": version.created_at}


@router.get("/documentos")
def list_documents(processo_id: int | None = Query(None, ge=1), q: str = Query("", max_length=200),
    limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
    session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    d, v, p = m.Documento, m.DocumentoArquivo, m.Processo
    latest = select(v.documento_id, func.max(v.id).label("version_id")).where(v.atual.is_(True)).group_by(v.documento_id).subquery()
    capture_latest = select(m.CapturaAutos.processo_instancia_id,
        func.max(m.CapturaAutos.generation).label("generation")).group_by(m.CapturaAutos.processo_instancia_id).subquery()
    included = select(m.ManifestoItem.documento_arquivo_id).join(m.CapturaAutos).join(capture_latest,
        and_(capture_latest.c.processo_instancia_id == m.CapturaAutos.processo_instancia_id,
             capture_latest.c.generation == m.CapturaAutos.generation)).where(m.CapturaAutos.status == "complete")
    stmt = select(d, v, m.DocumentoResumo, p.numero, m.Cliente.nome, m.ProcessoInstancia.grau,
        v.id.in_(included).label("included")).outerjoin(p, and_(p.id == d.processo_id,
            p.escritorio_id == current.escritorio_id)).outerjoin(m.Cliente,
        and_(m.Cliente.id == p.cliente_id, m.Cliente.escritorio_id == current.escritorio_id))
    stmt = stmt.outerjoin(latest, latest.c.documento_id == d.id).outerjoin(v, v.id == latest.c.version_id)
    stmt = stmt.outerjoin(m.DocumentoResumo, m.DocumentoResumo.documento_arquivo_id == v.id).outerjoin(
        m.ProcessoInstancia, m.ProcessoInstancia.id == d.processo_instancia_id).where(
        or_(d.escritorio_id == current.escritorio_id, and_(d.escritorio_id.is_(None), p.escritorio_id == current.escritorio_id)))
    if processo_id is not None:
        get_owned_or_404(session, p, processo_id, current)
        stmt = stmt.where(d.processo_id == processo_id)
    if q.strip():
        stmt = stmt.where(d.nome.icontains(q.strip(), autoescape=True))
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = session.execute(stmt.order_by(d.id.desc()).limit(limit).offset(offset)).all()
    return {"total": total, "items": [{"id": doc.id, "nome": doc.nome, "tipo": doc.tipo,
        "processo_id": doc.processo_id, "processo_numero": number, "cliente_nome": customer,
        "grau": degree, "no_contexto": bool(in_context), "versao": version_out(version, summary) if version else None}
        for doc, version, summary, number, customer, degree, in_context in rows]}


@router.get("/documentos/{documento_id}/versoes")
def document_versions(documento_id: int, limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
    session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    _get_owned_documento(session, documento_id, current)
    stmt = select(m.DocumentoArquivo, m.DocumentoResumo).outerjoin(m.DocumentoResumo,
        m.DocumentoResumo.documento_arquivo_id == m.DocumentoArquivo.id).where(m.DocumentoArquivo.documento_id == documento_id)
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = session.execute(stmt.order_by(m.DocumentoArquivo.id.desc()).limit(limit).offset(offset)).all()
    return {"items": [version_out(v, s) for v, s in rows], "total": total}


@router.get("/documentos/{documento_id}/versoes/{versao_id}/trechos")
def version_excerpts(documento_id: int, versao_id: int, pagina: int | None = Query(None, ge=1),
    q: str = Query("", max_length=200), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
    session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    from fastapi import HTTPException
    _get_owned_documento(session, documento_id, current)
    version = session.get(m.DocumentoArquivo, versao_id)
    if version is None or version.documento_id != documento_id:
        raise HTTPException(404, "versão não encontrada")
    stmt = select(m.DocumentoTrecho).where(m.DocumentoTrecho.documento_arquivo_id == versao_id)
    if pagina:
        stmt = stmt.where(m.DocumentoTrecho.pagina == pagina)
    if q.strip():
        stmt = stmt.where(m.DocumentoTrecho.texto.icontains(q.strip(), autoescape=True))
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    chunks = session.scalars(stmt.order_by(m.DocumentoTrecho.pagina, m.DocumentoTrecho.indice).limit(limit).offset(offset)).all()
    summary = session.scalar(select(m.DocumentoResumo).where(m.DocumentoResumo.documento_arquivo_id == versao_id))
    citations = []
    if summary and summary.status == "complete":
        raw = [c for c in (summary.citations or []) if isinstance(c, dict) and isinstance(c.get("chunk_id"), int)]
        pages = dict(session.execute(select(m.DocumentoTrecho.id, m.DocumentoTrecho.pagina).where(
            m.DocumentoTrecho.documento_arquivo_id == versao_id, m.DocumentoTrecho.id.in_([c["chunk_id"] for c in raw]))).all())
        citations = [{"chunk_id": c["chunk_id"], "pagina": pages[c["chunk_id"]], "quote": c.get("quote", "")}
            for c in raw if c["chunk_id"] in pages]
    return {"items": [{"id": c.id, "pagina": c.pagina, "texto": c.texto, "ocr": c.ocr} for c in chunks],
        "total": total, "resumo": summary.resumo if summary and summary.status == "complete" else None,
        "citations": citations,
        "versao": version_out(version, summary)}


@router.get("/tarefas/{tarefa_id}/documentos")
def task_documents(tarefa_id: int, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    get_owned_or_404(session, m.Tarefa, tarefa_id, current)
    rows = session.scalars(select(m.TarefaDocumento).where(m.TarefaDocumento.tarefa_id == tarefa_id,
        m.TarefaDocumento.escritorio_id == current.escritorio_id).order_by(m.TarefaDocumento.id.desc())).all()
    return [{"id": r.id, "nome": r.nome, "documento_id": r.documento_id,
             "documento_arquivo_id": r.documento_arquivo_id, "sha256": r.sha256, "created_at": r.created_at} for r in rows]
