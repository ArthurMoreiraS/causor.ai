"""Resumo estruturado por documento, com citações verificadas contra chunks.

Nenhuma citação inventada sobrevive: `validate_citations` confere que o quote
existe (normalizado) dentro do trecho persistido citado. Saída inválida marca
o resumo `failed` — nunca é aceita silenciosamente.
"""

from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.llm import get_provider
from app.settings import settings
from app.sor import models


class InvalidCitationError(ValueError):
    pass


class ChunkCitation(BaseModel):
    chunk_id: int
    quote: str = Field(min_length=5, max_length=500)


class DocumentDigest(BaseModel):
    resumo: str
    fatos: list[str]
    pedidos: list[str]
    decisoes: list[str]
    prazos: list[str]
    incertezas: list[str]
    citations: list[ChunkCitation]


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped).strip().lower()


def validate_citations(
    session: Session,
    digest: DocumentDigest,
    *,
    documento_arquivo_id: int | None = None,
) -> None:
    """Confere cada citação contra o chunk persistido; levanta se inventada."""
    for citation in digest.citations:
        chunk = session.get(models.DocumentoTrecho, citation.chunk_id)
        if chunk is None:
            raise InvalidCitationError(f"chunk {citation.chunk_id} nao existe")
        if (
            documento_arquivo_id is not None
            and chunk.documento_arquivo_id != documento_arquivo_id
        ):
            raise InvalidCitationError(
                f"chunk {citation.chunk_id} pertence a outra versao de documento"
            )
        if _normalize(citation.quote) not in _normalize(chunk.texto):
            raise InvalidCitationError(
                f"quote nao encontrado no chunk {citation.chunk_id}"
            )


_SYSTEM_PROMPT = (
    "Você resume documentos judiciais brasileiros para compor o dossiê de um "
    "processo. Responda somente com o schema pedido. Toda afirmação "
    "substantiva (fato, pedido, decisão, prazo) deve referenciar uma citação "
    "com o chunk_id fornecido e um quote LITERAL copiado do trecho. Nunca "
    "invente quote, nome de autoridade ou conteúdo que não esteja nos trechos."
)


def summarize_document(
    session: Session,
    *,
    version: models.DocumentoArquivo,
    provider=None,
) -> models.DocumentoResumo:
    """Gera (ou regenera) o resumo citado de uma versão extraída."""
    resumo_row = session.scalars(
        select(models.DocumentoResumo).where(
            models.DocumentoResumo.documento_arquivo_id == version.id
        )
    ).first()
    if resumo_row is None:
        resumo_row = models.DocumentoResumo(documento_arquivo_id=version.id)
        session.add(resumo_row)
        session.flush()

    if version.extraction_status != "complete":
        resumo_row.status = "failed"
        resumo_row.error = f"extraction_status={version.extraction_status}"
        session.flush()
        return resumo_row

    chunks = list(
        session.scalars(
            select(models.DocumentoTrecho)
            .where(models.DocumentoTrecho.documento_arquivo_id == version.id)
            .order_by(models.DocumentoTrecho.pagina, models.DocumentoTrecho.indice)
        )
    )
    if not chunks:
        resumo_row.status = "failed"
        resumo_row.error = "sem trechos extraidos"
        session.flush()
        return resumo_row

    documento = session.get(models.Documento, version.documento_id)
    numbered = "\n\n".join(
        f"[chunk_id={chunk.id} | pagina {chunk.pagina}]\n{chunk.texto}" for chunk in chunks
    )
    user_prompt = (
        f"Documento: {documento.nome if documento else version.documento_id} "
        f"(tipo: {documento.tipo if documento else 'desconhecido'})\n\n"
        f"Trechos numerados:\n\n{numbered}"
    )

    model_name = settings.claude_context_model
    llm = provider or get_provider(model=model_name)
    try:
        digest = llm.complete_structured(
            system=_SYSTEM_PROMPT,
            user=user_prompt,
            schema=DocumentDigest,
            max_tokens=3000,
        )
        validate_citations(session, digest, documento_arquivo_id=version.id)
    except InvalidCitationError as exc:
        resumo_row.status = "failed"
        resumo_row.error = str(exc)
        resumo_row.model = model_name
        session.flush()
        return resumo_row
    except Exception as exc:  # noqa: BLE001 - falha de LLM vira estado observável
        resumo_row.status = "failed"
        resumo_row.error = str(exc)[:2000]
        resumo_row.model = model_name
        session.flush()
        return resumo_row

    resumo_row.status = "complete"
    resumo_row.resumo = digest.resumo
    resumo_row.dados = {
        "fatos": digest.fatos,
        "pedidos": digest.pedidos,
        "decisoes": digest.decisoes,
        "prazos": digest.prazos,
        "incertezas": digest.incertezas,
    }
    resumo_row.citations = [citation.model_dump() for citation in digest.citations]
    resumo_row.model = model_name
    resumo_row.error = None
    session.flush()
    return resumo_row
