"""Contexto integral e citado do processo.

`ContextoProcesso.status="ready"` significa: toda instância requerida tem a
última captura `complete` (ou `not_applicable` com evidência), todo arquivo
atual está extraído e resumido com citações válidas, e o inventário cobre
100% dos arquivos. A seleção semântica afeta só os excertos; o inventário é
sempre integral.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.sor import models

EXPECTED_DEGREES: tuple[str, ...] = ("1", "2")


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
