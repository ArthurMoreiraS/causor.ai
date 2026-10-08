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

from app.agent.llm import LLMOutputInvalidError, get_provider
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


# Símbolos tipográficos equivalentes que o modelo troca ao copiar (n° x nº, aspas, travessões).
_EQUIVALENTS = str.maketrans({"°": "o", "º": "o", "ª": "a", "“": '"', "”": '"', "‘": "'", "’": "'",
                              "–": "-", "—": "-", "‐": "-", " ": " "})


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.translate(_EQUIVALENTS))
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped).strip().lower()


def _words(value: str) -> list[tuple[str, int, int]]:
    """Palavras normalizadas com a posição de cada uma no texto original."""
    return [(_normalize(m.group()), m.start(), m.end()) for m in re.finditer(r"\w+", value.translate(_EQUIVALENTS))]


def literal_span(quote: str, text: str) -> str | None:
    """Trecho literal da fonte que sustenta a citação, ou None se não houver.

    Aceita a citação contígua e também a que omite um aposto intermediário: as
    palavras da citação precisam aparecer na mesma ordem, numa janela curta do
    texto. O retorno é sempre o trecho original, nunca o texto do modelo.
    Paráfrase (palavras ausentes ou fora de ordem) é recusada.
    """
    if _normalize(quote) in _normalize(text):
        return quote
    wanted = [w for w, _, _ in _words(quote)]
    source = _words(text)
    if len(wanted) < 4:
        return None
    limit = int(len(wanted) * 1.6) + 6
    for start, (word, _, _) in enumerate(source):
        if word != wanted[0]:
            continue
        position, matched = start, 0
        while position < len(source) and position - start < limit and matched < len(wanted):
            if source[position][0] == wanted[matched]:
                matched += 1
            position += 1
        if matched == len(wanted):
            return text[source[start][1]:source[position - 1][2]]
    return None


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
    profile: str = "padrao"


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


def _summarize_batch(llm, prefix: str, batch: list, max_tokens: int) -> list[DocumentDigest]:
    """Resume uma parte; se a resposta vier cortada, resume as duas metades."""
    numbered = "\n\n".join(
        f"[chunk_id={chunk.id} | pagina {chunk.pagina}]\n{chunk.texto}" for chunk in batch
    )
    try:
        part = llm.complete_structured(
            system=_SYSTEM_PROMPT, user=prefix + numbered, schema=DocumentDigest, max_tokens=max_tokens,
        )
    except LLMOutputInvalidError:
        # Autos com muitas peças geram resumo maior que o limite de saída.
        if len(batch) < 2:
            raise
        half = len(batch) // 2
        return (_summarize_batch(llm, prefix, batch[:half], max_tokens)
                + _summarize_batch(llm, prefix, batch[half:], max_tokens))
    allowed = {chunk.id for chunk in batch}
    if not part.citations:
        raise InvalidCitationError("resumo sem fonte citada")
    if any(c.chunk_id not in allowed for c in part.citations):
        raise InvalidCitationError("citação de trecho não fornecido nesta parte")
    text_by_id = {c.id: c.texto for c in batch}
    kept = []
    for citation in part.citations:
        span = literal_span(citation.quote, text_by_id[citation.chunk_id])
        if span is not None:
            kept.append(ChunkCitation(chunk_id=citation.chunk_id, quote=span[:500]))
    if not kept:
        raise InvalidCitationError("nenhuma citação confere com o texto original")
    dropped = len(part.citations) - len(kept)
    incertezas = list(part.incertezas)
    if dropped:
        incertezas.append(f"{dropped} citação(ões) descartada(s) por não conferir(em) "
                          "literalmente com o texto; confira as afirmações correspondentes.")
    return [part.model_copy(update={"citations": kept, "incertezas": incertezas})]


def generate_summary(snapshot: SummaryInput, *, provider=None, profile: str = "padrao") -> SummaryResult:
    """Provider work and literal citation validation, with no database access."""
    if profile not in {"padrao", "aprofundada"}:
        raise ValueError("perfil de resumo inválido")
    task = "draft" if profile == "aprofundada" else "context"
    model_name = settings.claude_draft_model if task == "draft" else settings.claude_context_model
    if snapshot.extraction_status != "complete":
        return SummaryResult(None, model_name, error=f"extraction_status={snapshot.extraction_status}", profile=profile)
    if not snapshot.chunks:
        return SummaryResult(None, model_name, error="sem trechos extraidos", profile=profile)
    chunks = snapshot.chunks
    try:
        llm = provider or get_provider(model=model_name, task=task)
        model_name = getattr(llm, "_model", model_name)
        batches: list[list] = [[]]
        chars = 0
        for chunk in chunks:
            if chars + len(chunk.texto) > 40000 and batches[-1]:
                batches.append([])
                chars = 0
            batches[-1].append(chunk)
            chars += len(chunk.texto)
        max_tokens = 8000 if profile == "aprofundada" else 6000
        digests = [part for batch in batches
                   for part in _summarize_batch(llm, snapshot.prefix, batch, max_tokens)]
        digest = DocumentDigest(
            resumo="\n\n".join(d.resumo for d in digests),
            **{field: [item for d in digests for item in getattr(d, field)]
               for field in ("fatos", "pedidos", "decisoes", "prazos", "incertezas", "citations")},
        )
    except InvalidCitationError as exc:
        return SummaryResult(None, model_name, error=str(exc), profile=profile)
    except Exception as exc:  # noqa: BLE001 - falha de LLM vira estado observável
        return SummaryResult(None, model_name, error=type(exc).__name__, profile=profile)
    return SummaryResult(digest, model_name, parts=len(digests), profile=profile)


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
        "processamento": {"trechos": len(snapshot.chunks), "partes": result.parts, "perfil": result.profile},
    }
    resumo_row.citations = [citation.model_dump() for citation in digest.citations]
    resumo_row.error = None
    session.flush()
    return resumo_row


def summarize_document(session: Session, *, version: models.DocumentoArquivo, provider=None) -> models.DocumentoResumo:
    """Compatibility helper. Workers use the three stages with separate sessions."""
    snapshot = load_summary_input(session, version)
    return persist_summary(session, snapshot, generate_summary(snapshot, provider=provider))
