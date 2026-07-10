"""Trechos citáveis e busca lexical.

Chunks nunca cruzam páginas (a citação é `[DOC p.N]`); IDs persistidos são a
unidade canônica de citação. Busca usa FTS `portuguese` no PostgreSQL e
substring case-insensitive no SQLite (testes).
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy import delete, select, text as sa_text
from sqlalchemy.orm import Session

from app.autos.extraction import ExtractedPage
from app.sor import models

DEFAULT_MAX_CHARS = 4000
DEFAULT_OVERLAP = 400


@dataclass(frozen=True)
class Chunk:
    page: int
    indice: int
    text: str
    ocr: bool


def chunk_pages(
    pages: tuple[ExtractedPage, ...],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    """Divide cada página independentemente em janelas com sobreposição."""
    chunks: list[Chunk] = []
    for page in pages:
        text = page.text
        if len(text) <= max_chars:
            chunks.append(Chunk(page=page.page, indice=0, text=text, ocr=page.ocr))
            continue
        indice = 0
        start = 0
        while start < len(text):
            window = text[start : start + max_chars]
            chunks.append(Chunk(page=page.page, indice=indice, text=window, ocr=page.ocr))
            if start + max_chars >= len(text):
                break
            start += max_chars - overlap
            indice += 1
    return chunks


def persist_chunks(
    session: Session,
    *,
    version: models.DocumentoArquivo,
    pages: tuple[ExtractedPage, ...],
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[models.DocumentoTrecho]:
    """Reinsere os trechos da versão dentro de uma transação (idempotente)."""
    session.execute(
        delete(models.DocumentoTrecho).where(
            models.DocumentoTrecho.documento_arquivo_id == version.id
        )
    )
    rows: list[models.DocumentoTrecho] = []
    for chunk in chunk_pages(tuple(pages), max_chars=max_chars, overlap=overlap):
        rows.append(
            models.DocumentoTrecho(
                documento_arquivo_id=version.id,
                pagina=chunk.page,
                indice=chunk.indice,
                texto=chunk.text,
                texto_sha256=sha256(chunk.text.encode("utf-8")).hexdigest(),
                char_count=len(chunk.text),
                ocr=chunk.ocr,
            )
        )
    session.add_all(rows)
    session.flush()
    return rows


def search_process_chunks(
    session: Session,
    *,
    escritorio_id: int,
    processo_id: int,
    query: str,
    limit: int = 20,
) -> list[dict]:
    """Busca lexical nos trechos atuais de um processo (tenant-scoped)."""
    if not query.strip():
        return []

    base = (
        select(
            models.DocumentoTrecho.id,
            models.DocumentoTrecho.pagina,
            models.DocumentoTrecho.texto,
            models.DocumentoTrecho.ocr,
            models.Documento.nome,
            models.Documento.tipo,
        )
        .join(
            models.DocumentoArquivo,
            models.DocumentoArquivo.id == models.DocumentoTrecho.documento_arquivo_id,
        )
        .join(models.Documento, models.Documento.id == models.DocumentoArquivo.documento_id)
        .where(
            models.DocumentoArquivo.atual.is_(True),
            models.Documento.processo_id == processo_id,
            models.Documento.escritorio_id == escritorio_id,
        )
    )

    if session.bind is not None and session.bind.dialect.name == "postgresql":
        stmt = (
            base.where(
                sa_text(
                    "to_tsvector('portuguese', documento_trecho.texto) @@ "
                    "plainto_tsquery('portuguese', :query)"
                )
            )
            .order_by(
                sa_text(
                    "ts_rank_cd(to_tsvector('portuguese', documento_trecho.texto), "
                    "plainto_tsquery('portuguese', :query)) DESC"
                )
            )
            .limit(limit)
            .params(query=query)
        )
        rows = session.execute(stmt).all()
    else:
        # SQLite (testes): substring case-insensitive, score pela contagem.
        needle = query.lower()
        rows = [
            row
            for row in session.execute(base.limit(500)).all()
            if needle in row.texto.lower()
        ]
        rows.sort(key=lambda row: row.texto.lower().count(needle), reverse=True)
        rows = rows[:limit]

    return [
        {
            "trecho_id": row.id,
            "pagina": row.pagina,
            "texto": row.texto,
            "ocr": row.ocr,
            "documento_nome": row.nome,
            "documento_tipo": row.tipo,
        }
        for row in rows
    ]
