"""Contexto integral e citado do processo.

`ContextoProcesso.status="ready"` significa: toda instância requerida tem a
última captura `complete` (ou `not_applicable` com evidência), todo arquivo
atual está extraído e resumido com citações válidas, e o inventário cobre
100% dos arquivos. A seleção semântica afeta só os excertos; o inventário é
sempre integral.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.settings import settings
from app.sor import models

EXPECTED_DEGREES: tuple[str, ...] = ("1", "2")


class ContextNotReadyError(RuntimeError):
    """Contexto do processo incompleto/obsoleto: redação e protocolo bloqueiam."""

    def __init__(self, *, processo_id: int, missing: list[str]):
        super().__init__(f"process_context_incomplete: {missing}")
        self.code = "process_context_incomplete"
        self.processo_id = processo_id
        self.missing = missing


@dataclass(frozen=True)
class ContextBundle:
    contexto_id: int
    source_fingerprint: str
    inventory_text: str
    consolidated_text: str
    cited_excerpts: str
    citations: tuple[dict, ...]


def _latest_capture(
    session: Session, instancia: models.ProcessoInstancia
) -> models.CapturaAutos | None:
    return session.scalars(
        select(models.CapturaAutos)
        .where(models.CapturaAutos.processo_instancia_id == instancia.id)
        .order_by(desc(models.CapturaAutos.generation))
        .limit(1)
    ).first()


def _current_versions(
    session: Session, capture: models.CapturaAutos
) -> list[models.DocumentoArquivo]:
    items = session.scalars(
        select(models.ManifestoItem).where(models.ManifestoItem.captura_id == capture.id)
    ).all()
    versions: list[models.DocumentoArquivo] = []
    for item in items:
        if item.documento_arquivo_id is None:
            continue
        version = session.get(models.DocumentoArquivo, item.documento_arquivo_id)
        if version is not None and version.atual:
            versions.append(version)
    return versions


def compute_source_fingerprint(
    captures: list[models.CapturaAutos], versions: list[models.DocumentoArquivo]
) -> str:
    source_parts = [c.final_fingerprint or "" for c in captures] + [v.sha256 for v in versions]
    return sha256("\n".join(sorted(source_parts)).encode("utf-8")).hexdigest()


def build_process_context(
    session: Session, *, processo: models.Processo
) -> models.ContextoProcesso:
    """Constrói (e persiste) o contexto do processo com prova de cobertura."""
    missing: list[str] = []
    captures_ok: list[models.CapturaAutos] = []
    versions: list[models.DocumentoArquivo] = []

    instancias = session.scalars(
        select(models.ProcessoInstancia).where(
            models.ProcessoInstancia.processo_id == processo.id
        )
    ).all()
    by_degree: dict[str, list[models.ProcessoInstancia]] = {}
    for instancia in instancias:
        by_degree.setdefault(instancia.grau, []).append(instancia)

    for grau in EXPECTED_DEGREES:
        rows = by_degree.get(grau, [])
        if not rows:
            missing.append(f"instancia:{grau}")
            continue
        for instancia in rows:
            capture = _latest_capture(session, instancia)
            if capture is None:
                missing.append(f"instancia:{grau}:sem_captura")
                continue
            if capture.status == "not_applicable":
                if not capture.evidence:
                    missing.append(f"instancia:{grau}:not_applicable_sem_evidencia")
                continue
            if capture.status != "complete":
                missing.append(f"instancia:{grau}:captura_{capture.status}")
                continue
            captures_ok.append(capture)
            versions.extend(_current_versions(session, capture))

    documents_total = len(versions)
    documents_extracted = 0
    documents_summarized = 0
    inventario: list[dict] = []
    citations: list[dict] = []
    consolidated_blocks: list[str] = []
    excerpt_blocks: list[str] = []

    for version in versions:
        documento = session.get(models.Documento, version.documento_id)
        label = f"DOC-{version.documento_id}"
        inventario.append(
            {
                "documento_id": version.documento_id,
                "documento_arquivo_id": version.id,
                "nome": documento.nome if documento else None,
                "tipo": documento.tipo if documento else None,
                "sha256": version.sha256,
                "paginas": version.page_count,
                "extraction_status": version.extraction_status,
                "sigiloso": bool(documento.sigiloso) if documento else False,
            }
        )
        if version.extraction_status == "complete":
            documents_extracted += 1
        else:
            missing.append(f"documento:{version.documento_id}:{version.extraction_status}")
            continue

        resumo = session.scalars(
            select(models.DocumentoResumo).where(
                models.DocumentoResumo.documento_arquivo_id == version.id
            )
        ).first()
        if resumo is None or resumo.status != "complete":
            status = resumo.status if resumo else "sem_resumo"
            missing.append(f"documento:{version.documento_id}:resumo_{status}")
            continue
        documents_summarized += 1

        nome = documento.nome if documento else str(version.documento_id)
        consolidated_blocks.append(f"[{label}] {nome}: {resumo.resumo}")
        for citation in resumo.citations or []:
            chunk = session.get(models.DocumentoTrecho, citation.get("chunk_id"))
            pagina = chunk.pagina if chunk else None
            citations.append(
                {
                    "documento_id": version.documento_id,
                    "documento_arquivo_id": version.id,
                    "chunk_id": citation.get("chunk_id"),
                    "quote": citation.get("quote"),
                    "pagina": pagina,
                }
            )
            excerpt_blocks.append(f"[{label} p.{pagina}] \"{citation.get('quote')}\"")

    status = "ready" if not missing else "building"
    fingerprint = compute_source_fingerprint(captures_ok, versions)

    cobertura = {
        "documents_total": documents_total,
        "documents_extracted": documents_extracted,
        "documents_summarized": documents_summarized,
        "missing": missing,
        "instancias": {
            grau: [inst.id for inst in by_degree.get(grau, [])] for grau in EXPECTED_DEGREES
        },
    }

    header = (
        f"Processo {processo.numero}"
        + (f" · {processo.classe}" if processo.classe else "")
        + (f" · {processo.tribunal}" if processo.tribunal else "")
        + (f" · {processo.orgao_julgador}" if processo.orgao_julgador else "")
    )
    contexto_consolidado = "\n\n".join([header, *consolidated_blocks]) if not missing else None

    contexto = models.ContextoProcesso(
        escritorio_id=processo.escritorio_id,
        processo_id=processo.id,
        status=status,
        source_fingerprint=fingerprint,
        inventario=inventario,
        cobertura=cobertura,
        contexto_consolidado=contexto_consolidado,
        citations=citations,
        ready_at=datetime.now(timezone.utc) if status == "ready" else None,
    )
    session.add(contexto)
    session.flush()
    return contexto


def current_fingerprint(session: Session, *, processo: models.Processo) -> str:
    """Fingerprint do estado atual (capturas + arquivos), sem persistir nada."""
    captures: list[models.CapturaAutos] = []
    versions: list[models.DocumentoArquivo] = []
    instancias = session.scalars(
        select(models.ProcessoInstancia).where(
            models.ProcessoInstancia.processo_id == processo.id
        )
    ).all()
    for instancia in instancias:
        capture = _latest_capture(session, instancia)
        if capture is not None and capture.status == "complete":
            captures.append(capture)
            versions.extend(_current_versions(session, capture))
    return compute_source_fingerprint(captures, versions)


def latest_context(
    session: Session, *, processo: models.Processo
) -> models.ContextoProcesso | None:
    return session.scalars(
        select(models.ContextoProcesso)
        .where(models.ContextoProcesso.processo_id == processo.id)
        .order_by(desc(models.ContextoProcesso.id))
        .limit(1)
    ).first()


def _bundle_from_row(contexto: models.ContextoProcesso) -> ContextBundle:
    inventory_lines = ["Inventário integral dos autos (100% dos arquivos atuais):"]
    for item in contexto.inventario:
        inventory_lines.append(
            f"- [DOC-{item['documento_id']}] {item.get('nome')} "
            f"(tipo: {item.get('tipo') or 'desconhecido'}; páginas: {item.get('paginas')}; "
            f"sha256: {str(item.get('sha256'))[:12]}…)"
        )
    excerpts = "\n".join(
        f"[DOC-{c['documento_id']} p.{c.get('pagina')}] \"{c.get('quote')}\""
        for c in (contexto.citations or [])
    )
    return ContextBundle(
        contexto_id=contexto.id,
        source_fingerprint=contexto.source_fingerprint,
        inventory_text="\n".join(inventory_lines),
        consolidated_text=contexto.contexto_consolidado or "",
        cited_excerpts=excerpts,
        citations=tuple(contexto.citations or []),
    )


def get_ready_context(
    session: Session, *, processo: models.Processo
) -> ContextBundle | None:
    """Bundle do último contexto `ready` cujo fingerprint ainda é o atual."""
    contexto = latest_context(session, processo=processo)
    if contexto is None or contexto.status != "ready":
        return None
    if contexto.source_fingerprint != current_fingerprint(session, processo=processo):
        return None
    return _bundle_from_row(contexto)


def _audit(
    session: Session,
    *,
    escritorio_id: int | None,
    ator: str,
    acao: str,
    entidade: str,
    entidade_id: int,
    detalhe: dict | None = None,
) -> None:
    session.add(
        models.AuditLog(
            escritorio_id=escritorio_id,
            ator=ator,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            detalhe=detalhe or {},
        )
    )


def _court_update_after(
    session: Session, processo: models.Processo, moment: datetime
) -> bool:
    """Houve novidade do tribunal (intimação/andamento) depois de `moment`?"""
    newer_intimacao = session.scalars(
        select(models.Intimacao.id)
        .where(
            models.Intimacao.processo_id == processo.id,
            models.Intimacao.created_at > moment,
        )
        .limit(1)
    ).first()
    if newer_intimacao is not None:
        return True
    newer_andamento = session.scalars(
        select(models.Andamento.id)
        .where(
            models.Andamento.processo_id == processo.id,
            models.Andamento.created_at > moment,
        )
        .limit(1)
    ).first()
    return newer_andamento is not None


def _missing_reasons(session: Session, processo: models.Processo) -> list[str]:
    contexto = latest_context(session, processo=processo)
    if contexto is None:
        return ["contexto:inexistente"]
    if contexto.status != "ready":
        missing = list((contexto.cobertura or {}).get("missing", []))
        return missing or [f"contexto:{contexto.status}"]
    if contexto.source_fingerprint != current_fingerprint(session, processo=processo):
        return ["contexto:fingerprint_obsoleto"]

    ready_at = contexto.ready_at
    if ready_at is not None:
        if ready_at.tzinfo is None:
            ready_at = ready_at.replace(tzinfo=timezone.utc)
        age_limit = timedelta(hours=settings.context_freshness_hours)
        if datetime.now(timezone.utc) - ready_at > age_limit and _court_update_after(
            session, processo, contexto.ready_at
        ):
            return ["contexto:stale"]
    return []


def create_context_override(
    session: Session,
    *,
    processo: models.Processo,
    usuario_id: int,
    action: str,
    justification: str,
) -> models.ContextOverride:
    """Liberação excepcional: uso único, expira em 30 min, sempre auditada."""
    if not 20 <= len(justification) <= 1000:
        raise ValueError("justificativa deve ter entre 20 e 1000 caracteres")
    override = models.ContextOverride(
        escritorio_id=processo.escritorio_id,
        processo_id=processo.id,
        usuario_id=usuario_id,
        action=action,
        justification=justification,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    session.add(override)
    session.flush()
    _audit(
        session,
        escritorio_id=processo.escritorio_id,
        ator=f"usuario:{usuario_id}",
        acao="process_context_override_created",
        entidade="context_override",
        entidade_id=override.id,
        detalhe={"processo_id": processo.id, "action": action},
    )
    return override


def consume_context_override(
    session: Session,
    *,
    processo: models.Processo,
    usuario_id: int,
    action: str,
) -> models.ContextOverride | None:
    now = datetime.now(timezone.utc)
    override = session.scalars(
        select(models.ContextOverride)
        .where(
            models.ContextOverride.processo_id == processo.id,
            models.ContextOverride.usuario_id == usuario_id,
            models.ContextOverride.action == action,
            models.ContextOverride.consumed_at.is_(None),
        )
        .order_by(desc(models.ContextOverride.id))
    ).first()
    if override is None:
        return None
    expires_at = override.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        return None
    override.consumed_at = now
    _audit(
        session,
        escritorio_id=processo.escritorio_id,
        ator=f"usuario:{usuario_id}",
        acao="process_context_override_consumed",
        entidade="context_override",
        entidade_id=override.id,
        detalhe={
            "processo_id": processo.id,
            "action": action,
            "missing": _missing_reasons(session, processo),
        },
    )
    session.flush()
    return override


def require_ready_context(
    session: Session,
    *,
    processo: models.Processo | None,
    usuario_id: int | None,
    action: str,
) -> str:
    """Gate fail-closed: retorna "ready" ou "override"; senão levanta.

    Contexto incompleto/obsoleto bloqueia a ação, a menos que exista um
    override válido (uso único, 30 min) do advogado para esta exata ação.
    """
    if processo is None:
        raise ContextNotReadyError(processo_id=0, missing=["processo:inexistente"])
    missing = _missing_reasons(session, processo)
    if not missing:
        return "ready"
    if usuario_id is not None:
        override = consume_context_override(
            session, processo=processo, usuario_id=usuario_id, action=action
        )
        if override is not None:
            return "override"
    raise ContextNotReadyError(processo_id=processo.id, missing=missing)
