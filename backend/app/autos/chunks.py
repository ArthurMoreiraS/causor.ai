"""Trechos citáveis persistidos por página (unidade canônica de citação)."""

from __future__ import annotations

from hashlib import sha256

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.autos.extraction import ExtractedPage
from app.sor import models


def persist_chunks(
    session: Session,
    *,
    version: models.DocumentoArquivo,
    pages: tuple[ExtractedPage, ...],
) -> list[models.DocumentoTrecho]:
    """Reinsere os trechos da versão dentro de uma transação (idempotente)."""
    session.execute(
        delete(models.DocumentoTrecho).where(
            models.DocumentoTrecho.documento_arquivo_id == version.id
        )
    )
    rows: list[models.DocumentoTrecho] = []
    for page in pages:
        rows.append(
            models.DocumentoTrecho(
                documento_arquivo_id=version.id,
                pagina=page.page,
                indice=0,
                texto=page.text,
                texto_sha256=sha256(page.text.encode("utf-8")).hexdigest(),
                char_count=len(page.text),
                ocr=page.ocr,
            )
        )
    session.add_all(rows)
    session.flush()
    return rows
