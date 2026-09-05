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
    if not digest.citations:
        raise InvalidCitationError("resumo sem fonte citada")
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
    prefix = (
        f"Documento: {documento.nome if documento else version.documento_id} "
        f"(tipo: {documento.tipo if documento else 'desconhecido'})\n\n"
        "Trechos numerados desta parte do documento:\n\n"
    )

    model_name = settings.claude_context_model
    try:
        llm = provider or get_provider(model=model_name, task="context")
        model_name = getattr(llm, "_model", model_name)
        batches: list[list] = [[]]
        chars = 0
        for chunk in chunks:
            if chars + len(chunk.texto) > 40000 and batches[-1]:
                batches.append([])
                chars = 0
            batches[-1].append(chunk)
            chars += len(chunk.texto)
        digests = []
        for batch in batches:
            numbered = "\n\n".join(
                f"[chunk_id={chunk.id} | pagina {chunk.pagina}]\n{chunk.texto}" for chunk in batch
            )
            part = llm.complete_structured(
                system=_SYSTEM_PROMPT, user=prefix + numbered,
                schema=DocumentDigest, max_tokens=3000,
            )
            validate_citations(session, part, documento_arquivo_id=version.id)
            allowed = {chunk.id for chunk in batch}
            if any(c.chunk_id not in allowed for c in part.citations):
                raise InvalidCitationError("citação de trecho não fornecido nesta parte")
            digests.append(part)
        digest = DocumentDigest(
            resumo="\n\n".join(d.resumo for d in digests),
            **{field: [item for d in digests for item in getattr(d, field)]
               for field in ("fatos", "pedidos", "decisoes", "prazos", "incertezas", "citations")},
        )
    except InvalidCitationError as exc:
        resumo_row.status = "failed"
        resumo_row.error = str(exc)
        resumo_row.model = model_name
        session.flush()
        return resumo_row
    except Exception as exc:  # noqa: BLE001 - falha de LLM vira estado observável
        resumo_row.status = "failed"
        resumo_row.error = type(exc).__name__
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
        "processamento": {"trechos": len(chunks), "partes": len(batches)},
    }
    resumo_row.citations = [citation.model_dump() for citation in digest.citations]
    resumo_row.model = model_name
    resumo_row.error = None
    session.flush()
    return resumo_row
