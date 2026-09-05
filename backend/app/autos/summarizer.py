"""Resumo estruturado por documento, com citações verificadas contra chunks.

Nenhuma citação inventada sobrevive: `validate_citations` confere que o quote
existe (normalizado) dentro do trecho persistido citado. Saída inválida marca
o resumo `failed` — nunca é aceita silenciosamente.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

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


@dataclass(frozen=True)
class SummaryChunk:
    id: int
    pagina: int
    texto: str


@dataclass(frozen=True)
class SummaryInput:
    version_id: int
    sha256: str
    extraction_status: str
    prefix: str
    chunks: tuple[SummaryChunk, ...]


@dataclass(frozen=True)
class SummaryResult:
    digest: DocumentDigest | None
    model: str
    parts: int = 0
    error: str | None = None


def load_summary_input(session: Session, version: models.DocumentoArquivo) -> SummaryInput:
    """Copy the inputs; no ORM instances/connections escape the read session."""
    chunks = list(
        session.scalars(
            select(models.DocumentoTrecho)
            .where(models.DocumentoTrecho.documento_arquivo_id == version.id)
            .order_by(models.DocumentoTrecho.pagina, models.DocumentoTrecho.indice)
        )
    )
    documento = session.get(models.Documento, version.documento_id)
    prefix = (
        f"Documento: {documento.nome if documento else version.documento_id} "
        f"(tipo: {documento.tipo if documento else 'desconhecido'})\n\n"
        "Trechos numerados desta parte do documento:\n\n"
    )

    return SummaryInput(version.id, version.sha256, version.extraction_status, prefix,
                        tuple(SummaryChunk(c.id, c.pagina, c.texto) for c in chunks))


def generate_summary(snapshot: SummaryInput, *, provider=None) -> SummaryResult:
    """Provider work and literal citation validation, with no database access."""
    model_name = settings.claude_context_model
    if snapshot.extraction_status != "complete":
        return SummaryResult(None, model_name, error=f"extraction_status={snapshot.extraction_status}")
    if not snapshot.chunks:
        return SummaryResult(None, model_name, error="sem trechos extraidos")
    chunks = snapshot.chunks
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
                system=_SYSTEM_PROMPT, user=snapshot.prefix + numbered,
                schema=DocumentDigest, max_tokens=3000,
            )
            allowed = {chunk.id for chunk in batch}
            if not part.citations:
                raise InvalidCitationError("resumo sem fonte citada")
            if any(c.chunk_id not in allowed for c in part.citations):
                raise InvalidCitationError("citação de trecho não fornecido nesta parte")
            text_by_id = {c.id: c.texto for c in batch}
            for citation in part.citations:
                if _normalize(citation.quote) not in _normalize(text_by_id[citation.chunk_id]):
                    raise InvalidCitationError(f"quote nao encontrado no chunk {citation.chunk_id}")
            digests.append(part)
        digest = DocumentDigest(
            resumo="\n\n".join(d.resumo for d in digests),
            **{field: [item for d in digests for item in getattr(d, field)]
               for field in ("fatos", "pedidos", "decisoes", "prazos", "incertezas", "citations")},
        )
    except InvalidCitationError as exc:
        return SummaryResult(None, model_name, error=str(exc))
    except Exception as exc:  # noqa: BLE001 - falha de LLM vira estado observável
        return SummaryResult(None, model_name, error=type(exc).__name__)
    return SummaryResult(digest, model_name, parts=len(batches))


def persist_summary(session: Session, snapshot: SummaryInput, result: SummaryResult) -> models.DocumentoResumo:
    """Caller holds ownership. Serialize duplicate jobs on the same version."""
    version = session.scalar(select(models.DocumentoArquivo).where(
        models.DocumentoArquivo.id == snapshot.version_id,
    ).with_for_update().execution_options(populate_existing=True))
    if version is None or load_summary_input(session, version) != snapshot:
        raise InvalidCitationError("summary_input_changed")
    resumo_row = session.scalar(select(models.DocumentoResumo).where(
        models.DocumentoResumo.documento_arquivo_id == snapshot.version_id,
    ))
    if resumo_row is None:
        resumo_row = models.DocumentoResumo(documento_arquivo_id=snapshot.version_id)
        session.add(resumo_row)
    resumo_row.model = result.model
    digest = result.digest
    if digest is None:
        resumo_row.status = "failed"
        resumo_row.error = result.error
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
        "processamento": {"trechos": len(snapshot.chunks), "partes": result.parts},
    }
    resumo_row.citations = [citation.model_dump() for citation in digest.citations]
    resumo_row.error = None
    session.flush()
    return resumo_row


def summarize_document(session: Session, *, version: models.DocumentoArquivo, provider=None) -> models.DocumentoResumo:
    """Compatibility helper. Workers use the three stages with separate sessions."""
    snapshot = load_summary_input(session, version)
    return persist_summary(session, snapshot, generate_summary(snapshot, provider=provider))
