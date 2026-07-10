# Autos integrais, OCR e contexto citado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capturar e provar a integridade dos autos de primeiro/segundo grau, extrair todo PDF por página, construir um contexto citado e bloquear redação/protocolo sempre que houver lacuna não autorizada.

**Architecture:** Uma captura possui enumeração inicial, itens normalizados, versões imutáveis por SHA-256 e enumeração final. O agente envia arquivos diretamente ao storage; o backend baixa, recomputa hash, valida PDF, extrai texto/OCR e cria trechos citáveis. Um `ContextoProcesso` só fica `ready` quando todas as instâncias requeridas estão completas e todos os arquivos atuais estão extraídos e resumidos com citações válidas.

**Tech Stack:** SQLAlchemy/Alembic, S3/Supabase Storage, PyMuPDF, Pillow, pytesseract/Tesseract `por`, PostgreSQL Full Text Search, Pydantic structured output, FastAPI, Next.js.

## Global Constraints

- Depende integralmente do Marco A do plano `2026-07-10-fundacao-automacao-judicial-agente-local.md`.
- `CapturaAutos.status=complete` significa integridade binária; `ContextoProcesso.status=ready` significa extração e cobertura sem falhas.
- Enumeração inicial/final deve usar IDs estáveis do portal e `source_fingerprint` SHA-256.
- `cursor_complete=False` nunca pode resultar em captura completa.
- Documento listado mas sem download verificado deixa a captura `incomplete`.
- HTML de erro/login salvo com extensão `.pdf` é rejeitado por magic bytes.
- Arquivo não PDF é armazenado e hasheado quando listado pelo portal, mas recebe `extraction_status=unsupported_mime`; nunca é omitido e bloqueia `ContextoProcesso.ready` até existir extrator ou revisão documentada.
- Cada versão é imutável; o storage não depende de versionamento S3.
- OCR roda somente nas páginas sem camada textual útil.
- Toda citação guarda `documento_arquivo_id`, página, trecho e quote verificável.
- Inventário de 100% dos documentos entra no dossiê; seleção semântica afeta apenas os excertos verbatim.
- Resumo não pode citar quote inexistente no trecho persistido.
- Redação e protocolo exigem `ContextoProcesso.ready` e fingerprint atual.
- Override é de uso único, expira em 30 minutos, exige justificativa de 20–1000 caracteres e produz auditoria.
- Sem embeddings pagos nesta fase; busca lexical PostgreSQL com fallback SQLite em testes.

---

## File map

**Create**

- `backend/alembic/versions/b7d5e9f3a2c1_autos_contexto_integral.py`
- `backend/app/autos/contracts.py` — manifestos recebidos do agente.
- `backend/app/autos/service.py` — abertura, ingestão, conferência e finalização.
- `backend/app/autos/integrity.py` — fingerprint, PDF/hash e regras de completude.
- `backend/app/autos/extraction.py` — texto/OCR por página.
- `backend/app/autos/worker.py` — processamento persistente fora do request HTTP.
- `backend/app/autos/chunks.py` — chunking e busca lexical.
- `backend/app/autos/summarizer.py` — resumo estruturado com citações validadas.
- `backend/app/autos/context.py` — `ContextBundle` e prontidão do processo.
- `backend/app/api/autos_routes.py` — endpoints de usuário e agente.
- `backend/tests/test_autos_models.py`
- `backend/tests/test_autos_integrity.py`
- `backend/tests/test_autos_service.py`
- `backend/tests/test_pdf_extraction.py`
- `backend/tests/test_autos_worker.py`
- `backend/tests/test_document_chunks.py`
- `backend/alembic/versions/c8e6f0a4b3d2_documento_trecho_fts.py`
- `backend/tests/test_document_summaries.py`
- `backend/tests/test_process_context.py`
- `backend/tests/test_draft_context_gate.py`
- `backend/tests/fixtures/pdfs/textual.pdf`
- `backend/tests/fixtures/pdfs/scanned.pdf`
- `frontend/app/components/ProcessContextStatus.tsx`
- `frontend/app/components/ProcessContextStatus.test.tsx`
- `backend/tests/test_document_access.py`

**Modify**

- `backend/app/sor/models.py` — captura, versões, itens, trechos, resumos, contexto e override.
- `backend/app/settings.py` — OCR, limites, freshness e gate.
- `backend/pyproject.toml` — PyMuPDF, Pillow, pytesseract.
- `backend/.env.example` — Tesseract e contexto.
- `backend/app/api/main.py` — incluir router e mapear erro de gate.
- `backend/app/cli.py` — worker `process-autos-due` e purge explícito.
- `backend/app/agent/service.py` — substituir histórico limitado por `ContextBundle`.
- `backend/app/agent/drafter.py` — prompt com inventário/citações.
- `backend/app/queue/jobs.py` — bloquear protocolo com contexto obsoleto/incompleto.
- `backend/tests/conftest.py` — helper de contexto completo.
- `backend/tests/test_agent.py`
- `backend/tests/test_agent_service.py`
- `frontend/lib/api.ts` — status/captura/override.
- `frontend/app/views/ProcessosView.tsx` — painel de contexto.

---

### Task 1: Persistência imutável de captura, documentos e contexto

**Files:**

- Modify: `backend/app/sor/models.py`
- Create: `backend/alembic/versions/b7d5e9f3a2c1_autos_contexto_integral.py`
- Create: `backend/tests/test_autos_models.py`

**Interfaces:**

- Produces: `CapturaAutos`, `DocumentoArquivo`, `ManifestoItem`, `DocumentoTrecho`, `DocumentoResumo`, `ContextoProcesso`, `ContextOverride`.
- Extends: `Documento` with tenant, instance and external identity while preserving `nome`, `tipo`, `uri`.

- [ ] **Step 1: Write failing persistence tests**

```python
# backend/tests/test_autos_models.py
from sqlalchemy.exc import IntegrityError
import pytest

from app.sor import models


def _instance(db_session, seeded):
    instance = models.ProcessoInstancia(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_base="https://example.invalid/pje",
        status="active",
    )
    db_session.add(instance)
    db_session.flush()
    return instance


def test_document_external_id_is_unique_inside_instance(db_session, seeded):
    instance = _instance(db_session, seeded)
    values = dict(
        escritorio_id=seeded.escritorio_id,
        processo_id=seeded.id,
        processo_instancia_id=instance.id,
        external_id="doc-1",
        nome="Decisão.pdf",
        tipo="Decisão",
        ordem=1,
        sigiloso=False,
    )
    db_session.add(models.Documento(**values))
    db_session.flush()
    db_session.add(models.Documento(**values))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_document_versions_are_immutable_by_hash(db_session, seeded):
    instance = _instance(db_session, seeded)
    document = models.Documento(
        escritorio_id=seeded.escritorio_id,
        processo_id=seeded.id,
        processo_instancia_id=instance.id,
        external_id="doc-1",
        nome="Decisão.pdf",
        ordem=1,
        sigiloso=False,
    )
    capture = models.CapturaAutos(
        escritorio_id=seeded.escritorio_id,
        processo_instancia_id=instance.id,
        status="downloading",
        generation=1,
    )
    db_session.add_all([document, capture])
    db_session.flush()
    version = models.DocumentoArquivo(
        documento_id=document.id,
        captura_id=capture.id,
        sha256="a" * 64,
        storage_key="tenant/1/doc.pdf",
        uri="s3://private/doc.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        extraction_status="pending",
        atual=True,
    )
    db_session.add(version)
    db_session.flush()
    assert version.atual is True
```

- [ ] **Step 2: Run and verify schema failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_autos_models.py -v`

Expected: FAIL because autos models/columns do not exist.

- [ ] **Step 3: Add exact model contracts**

Extend `Documento`:

```python
__table_args__ = (
    UniqueConstraint("processo_instancia_id", "external_id", name="uq_documento_external"),
)
escritorio_id: Mapped[int | None] = mapped_column(ForeignKey("escritorio.id"), index=True)
processo_instancia_id: Mapped[int | None] = mapped_column(ForeignKey("processo_instancia.id"), index=True)
external_id: Mapped[str | None] = mapped_column(String(255))
parent_external_id: Mapped[str | None] = mapped_column(String(255))
ordem: Mapped[int | None] = mapped_column(Integer)
data_documento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
sigiloso: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
metadados: Mapped[dict | None] = mapped_column(JSON)
```

Add models:

```python
class CapturaAutos(TimestampMixin, Base):
    __tablename__ = "captura_autos"
    __table_args__ = (
        UniqueConstraint("processo_instancia_id", "generation", name="uq_captura_autos_generation"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorio.id"), nullable=False, index=True)
    processo_instancia_id: Mapped[int] = mapped_column(ForeignKey("processo_instancia.id"), nullable=False, index=True)
    agent_command_id: Mapped[int | None] = mapped_column(ForeignKey("agent_command.id"))
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", index=True)
    initial_fingerprint: Mapped[str | None] = mapped_column(String(71))
    final_fingerprint: Mapped[str | None] = mapped_column(String(71))
    expected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    captured_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cursor_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    evidence: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentoArquivo(TimestampMixin, Base):
    __tablename__ = "documento_arquivo"
    __table_args__ = (
        UniqueConstraint("documento_id", "sha256", name="uq_documento_arquivo_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    documento_id: Mapped[int] = mapped_column(ForeignKey("documento.id"), nullable=False, index=True)
    captura_id: Mapped[int] = mapped_column(ForeignKey("captura_autos.id"), nullable=False, index=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    text_sha256: Mapped[str | None] = mapped_column(String(64))
    extraction_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    extraction_error: Mapped[str | None] = mapped_column(Text)
    atual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class ManifestoItem(TimestampMixin, Base):
    __tablename__ = "manifesto_item"
    __table_args__ = (
        UniqueConstraint("captura_id", "external_id", name="uq_manifesto_item_external"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    captura_id: Mapped[int] = mapped_column(ForeignKey("captura_autos.id"), nullable=False, index=True)
    documento_id: Mapped[int] = mapped_column(ForeignKey("documento.id"), nullable=False)
    documento_arquivo_id: Mapped[int | None] = mapped_column(ForeignKey("documento_arquivo.id"))
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    error_code: Mapped[str | None] = mapped_column(String(80))


class DocumentoTrecho(TimestampMixin, Base):
    __tablename__ = "documento_trecho"
    __table_args__ = (
        UniqueConstraint("documento_arquivo_id", "pagina", "indice", name="uq_documento_trecho_posicao"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    documento_arquivo_id: Mapped[int] = mapped_column(ForeignKey("documento_arquivo.id"), nullable=False, index=True)
    pagina: Mapped[int] = mapped_column(Integer, nullable=False)
    indice: Mapped[int] = mapped_column(Integer, nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    texto_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ocr: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DocumentoResumo(TimestampMixin, Base):
    __tablename__ = "documento_resumo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    documento_arquivo_id: Mapped[int] = mapped_column(ForeignKey("documento_arquivo.id"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    resumo: Mapped[str | None] = mapped_column(Text)
    dados: Mapped[dict | None] = mapped_column(JSON)
    citations: Mapped[list | None] = mapped_column(JSON)
    model: Mapped[str | None] = mapped_column(String(100))
    error: Mapped[str | None] = mapped_column(Text)


class ContextoProcesso(TimestampMixin, Base):
    __tablename__ = "contexto_processo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorio.id"), nullable=False, index=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processo.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="building")
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    inventario: Mapped[list] = mapped_column(JSON, nullable=False)
    cobertura: Mapped[dict] = mapped_column(JSON, nullable=False)
    contexto_consolidado: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSON)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ContextOverride(TimestampMixin, Base):
    __tablename__ = "context_override"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorio.id"), nullable=False, index=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processo.id"), nullable=False, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

The migration uses `down_revision="a6c4d8e2f1b0"`, backfills `documento.escritorio_id` through `processo`/`peticao`, and keeps new identity columns nullable for legacy/demo documents.

- [ ] **Step 4: Apply migration and run tests**

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m pytest tests/test_autos_models.py -q
```

Expected: PASS; Alembic head is `b7d5e9f3a2c1`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/sor/models.py backend/alembic/versions/b7d5e9f3a2c1_autos_contexto_integral.py backend/tests/test_autos_models.py
git commit -m "feat(autos): model immutable captures documents and contexts"
```

---

### Task 2: Fingerprint, normalização e prova de completude

**Files:**

- Create: `backend/app/autos/__init__.py`
- Create: `backend/app/autos/contracts.py`
- Create: `backend/app/autos/integrity.py`
- Create: `backend/tests/test_autos_integrity.py`

**Interfaces:**

- Produces: `ManifestDocumentInput`, `ManifestInput`, `fingerprint_manifest`, `validate_pdf`, `completeness_result`.

- [ ] **Step 1: Write deterministic integrity tests**

```python
# backend/tests/test_autos_integrity.py
import pytest

from app.autos.contracts import ManifestDocumentInput, ManifestInput
from app.autos.integrity import InvalidPdfError, fingerprint_manifest, validate_pdf


def _manifest(order=("a", "b")):
    return ManifestInput(
        cursor_complete=True,
        documents=[
            ManifestDocumentInput(
                external_id=value,
                nome=f"{value}.pdf",
                tipo=None,
                ordem=index,
                parent_external_id=None,
                data_documento=None,
                sigiloso=False,
                mime_type="application/pdf",
                size_hint=None,
                download_ref=f"opaque:{value}",
            )
            for index, value in enumerate(order, start=1)
        ],
        evidence={},
    )


def test_manifest_fingerprint_is_ordered_and_deterministic():
    assert fingerprint_manifest(_manifest()) == fingerprint_manifest(_manifest())
    assert fingerprint_manifest(_manifest()) != fingerprint_manifest(_manifest(("b", "a")))


def test_html_login_page_is_not_accepted_as_pdf():
    with pytest.raises(InvalidPdfError):
        validate_pdf(b"<html>login</html>", declared_mime="application/pdf")
```

- [ ] **Step 2: Run and verify missing modules**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_autos_integrity.py -v`

Expected: FAIL on import.

- [ ] **Step 3: Implement canonical fingerprint and PDF validation**

`ManifestDocumentInput`/`ManifestInput` are Pydantic models with `extra="forbid"`. `fingerprint_manifest` serializes only ordered stable fields using JSON `sort_keys=True`, UTF-8 and compact separators, returning `sha256:<hex>`.

`validate_pdf` must implement:

```python
def validate_pdf(data: bytes, *, declared_mime: str | None) -> None:
    if not data.startswith(b"%PDF-"):
        raise InvalidPdfError("download is not a PDF")
    if b"%%EOF" not in data[-4096:]:
        raise InvalidPdfError("PDF has no EOF marker")
    if declared_mime not in {None, "application/pdf", "application/octet-stream"}:
        raise InvalidPdfError(f"unexpected MIME type: {declared_mime}")
```

`completeness_result(initial, final, item_statuses)` returns `complete=False` when either cursor is incomplete, fingerprints differ, an external ID is missing/extra or any item is not `verified`. It returns exact lists `missing`, `extra`, `failed` for audit.

- [ ] **Step 4: Run integrity tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_autos_integrity.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/autos backend/tests/test_autos_integrity.py
git commit -m "feat(autos): add deterministic manifest integrity rules"
```

---

### Task 3: Orquestração resumível da captura e endpoints do agente

**Files:**

- Create: `backend/app/autos/service.py`
- Create: `backend/app/api/autos_routes.py`
- Modify: `backend/app/api/main.py`
- Create: `backend/tests/test_autos_service.py`
- Create: `backend/tests/test_autos_api.py`

**Interfaces:**

- User API: `POST /processos/{id}/autos/capturar`, `GET /processos/{id}/autos/status`.
- Agent API: `PUT /agent/captures/{id}/manifest/initial`, `POST /agent/captures/{id}/documents/{external_id}/upload-ticket`, `POST /agent/captures/{id}/documents/{external_id}/confirm`, `PUT /agent/captures/{id}/manifest/final`.
- Produces: `open_capture`, `record_initial_manifest`, `issue_document_ticket`, `confirm_document_upload`, `finalize_capture`.

- [ ] **Step 1: Write service test using two identical manifests**

```python
def test_capture_only_completes_after_same_final_manifest(
    db_session, seeded, object_store, complete_manifest
):
    capture = open_capture(db_session, processo_instancia=seeded["instance"], usuario_id=1)
    record_initial_manifest(db_session, capture=capture, manifest=complete_manifest)
    for item in capture.items:
        data = b"%PDF-1.4\n" + item.external_id.encode("utf-8") + b"\n%%EOF\n"
        digest = sha256(data).hexdigest()
        key = f"test/{item.external_id}.pdf"
        object_store.put_bytes(key, data, "application/pdf")
        confirm_document_upload(
            db_session,
            capture=capture,
            external_id=item.external_id,
            object_key=key,
            reported_sha256=digest,
            object_store=object_store,
        )
    result = finalize_capture(
        db_session, capture=capture, final_manifest=complete_manifest
    )
    assert result.status == "complete"
    assert result.missing_count == 0
```

Import `sha256` from `hashlib`. The fixture store returns the exact minimal PDFs written in the loop, and `confirm_document_upload` recomputes each hash instead of trusting `reported_sha256`.

- [ ] **Step 2: Run and verify missing service**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_autos_service.py -v`

Expected: FAIL on import.

- [ ] **Step 3: Implement state transitions and routes**

Use this state machine:

```python
CAPTURE_TRANSITIONS = {
    "queued": {"enumerating", "not_applicable", "failed"},
    "enumerating": {"downloading", "not_applicable", "incomplete", "failed"},
    "downloading": {"verifying", "incomplete", "failed"},
    "verifying": {"complete", "incomplete", "failed"},
    "complete": set(),
    "not_applicable": set(),
    "incomplete": set(),
    "failed": set(),
}
```

The user endpoint accepts `graus: ["1", "2"]` by default and creates/reuses a `ProcessoInstancia` for each requested degree before opening captures. A missing second-degree route remains pending until the connector returns `not_applicable` with evidence; absence of a row is never interpreted as completeness. `open_capture` increments `generation`, creates `CapturaAutos`, and enqueues `read_process` with payload containing only `capture_id`, `processo_instancia_id`, `sistema`, `tribunal`, `grau`, `numero_processo`, `url_base`.

`record_initial_manifest` upserts logical `Documento` rows and creates one `ManifestoItem` per external ID. Do not download inside the transaction.

`confirm_document_upload`:

1. loads bytes from `ObjectStore`;
2. validates size and PDF;
3. recomputes SHA-256;
4. rejects mismatch with `hash_mismatch`;
5. marks previous versions of the logical document `atual=False`;
6. inserts/reuses `DocumentoArquivo(documento_id, sha256)`;
7. marks item `verified`.

`finalize_capture` stores final fingerprint and calls `completeness_result`; only exact equality yields `complete`.

All routes validate office through agent installation or `CurrentUser`. Route bodies use Pydantic `extra="forbid"`; `download_ref` remains only in the agent command/session and is not exposed to frontend.

- [ ] **Step 4: Run service/API tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_autos_service.py tests/test_autos_api.py -q
```

Expected: PASS for complete, changed manifest, missing file, cross-tenant 404 and idempotent confirmations.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/autos/service.py backend/app/api/autos_routes.py backend/app/api/main.py backend/tests/test_autos_service.py backend/tests/test_autos_api.py
git commit -m "feat(autos): orchestrate resumable verified process capture"
```

---

### Task 4: Extração textual e OCR por página

**Files:**

- Modify: `backend/pyproject.toml`
- Modify: `backend/app/settings.py`
- Modify: `backend/.env.example`
- Create: `backend/app/autos/extraction.py`
- Create: `backend/app/autos/worker.py`
- Create: `backend/tests/test_pdf_extraction.py`
- Create: `backend/tests/test_autos_worker.py`
- Create: `backend/tests/fixtures/pdfs/textual.pdf`
- Create: `backend/tests/fixtures/pdfs/scanned.pdf`

**Interfaces:**

- Produces: `ExtractedPage`, `ExtractionResult`, `extract_pdf_pages`.
- Produces: `run_document_processing_job` and CLI `process-autos-due`; upload requests never execute OCR inline.

- [ ] **Step 1: Add failing extraction tests**

```python
from app.autos.extraction import extract_pdf_pages


def test_extracts_text_with_page_numbers(textual_pdf_bytes):
    result = extract_pdf_pages(textual_pdf_bytes)
    assert result.page_count == 2
    assert result.pages[0].page == 1
    assert "CONTRATO" in result.pages[0].text
    assert result.pages[0].ocr is False


def test_uses_ocr_only_for_page_without_text(scanned_pdf_bytes, monkeypatch):
    monkeypatch.setattr("app.autos.extraction._ocr_image", lambda image: "TEXTO OCR")
    result = extract_pdf_pages(scanned_pdf_bytes)
    assert result.pages[0].text == "TEXTO OCR"
    assert result.pages[0].ocr is True
```

- [ ] **Step 2: Add dependencies and verify failure**

Add:

```toml
"PyMuPDF>=1.24",
"Pillow>=10.4",
"pytesseract>=0.3.13",
```

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pdf_extraction.py -v`

Expected: FAIL because extraction module is missing.

- [ ] **Step 3: Implement page-aware extraction**

```python
@dataclass(frozen=True)
class ExtractedPage:
    page: int
    text: str
    ocr: bool


@dataclass(frozen=True)
class ExtractionResult:
    page_count: int
    pages: tuple[ExtractedPage, ...]
    text_sha256: str
```

Algorithm:

```python
with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
    pages = []
    for index, page in enumerate(document, start=1):
        text = page.get_text("text").strip()
        used_ocr = False
        if len(text) < settings.ocr_min_text_chars:
            pix = page.get_pixmap(dpi=settings.ocr_dpi, alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = _ocr_image(image).strip()
            used_ocr = True
        if not text:
            raise PdfExtractionError(f"page {index} has no extractable text")
        pages.append(ExtractedPage(page=index, text=text, ocr=used_ocr))
```

Use `pytesseract.image_to_string(image, lang=settings.tesseract_language)` and honor optional `settings.tesseract_cmd`. Add defaults: `ocr_min_text_chars=30`, `ocr_dpi=200`, `tesseract_language="por"`, `tesseract_cmd=""`.

`confirm_document_upload` enqueues a persistent `JobExecucao(tipo="process_document")` and returns. `run_document_processing_job` uses `ObjectStore.download_to()` to a temporary file while computing hash in 1 MiB blocks, enforces `settings.document_max_bytes` before PyMuPDF, processes one page at a time and deletes the temp file in `finally`. Add defaults `document_max_bytes=262144000`, `document_processing_attempts=3`, `document_processing_concurrency=1`. The CLI claims due jobs with `with_for_update(skip_locked=True)`, retries exponential backoff and never holds a database transaction during OCR/LLM work.

- [ ] **Step 4: Run extraction tests**

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests/test_pdf_extraction.py tests/test_autos_worker.py -q
```

Expected: PASS without invoking the machine Tesseract in unit tests; live OCR smoke runs separately.

- [ ] **Step 5: Commit**

```powershell
git add backend/pyproject.toml backend/app/settings.py backend/.env.example backend/app/autos/extraction.py backend/app/autos/worker.py backend/app/cli.py backend/tests/test_pdf_extraction.py backend/tests/test_autos_worker.py backend/tests/fixtures/pdfs
git commit -m "feat(autos): extract and OCR every PDF page"
```

---

### Task 5: Trechos citáveis e busca lexical

**Files:**

- Create: `backend/app/autos/chunks.py`
- Create: `backend/tests/test_document_chunks.py`
- Create: `backend/alembic/versions/c8e6f0a4b3d2_documento_trecho_fts.py`

**Interfaces:**

- Produces: `chunk_pages`, `persist_chunks`, `search_process_chunks`.
- Chunk IDs persistidos são a unidade canônica de citação.

- [ ] **Step 1: Write failing chunk tests**

```python
def test_chunks_never_cross_page_boundaries():
    pages = (
        ExtractedPage(page=1, text="A" * 4500, ocr=False),
        ExtractedPage(page=2, text="B" * 100, ocr=True),
    )
    chunks = chunk_pages(pages, max_chars=4000, overlap=400)
    assert [c.page for c in chunks] == [1, 1, 2]
    assert chunks[0].text[-400:] == chunks[1].text[:400]
    assert chunks[2].ocr is True
```

- [ ] **Step 2: Run and verify missing functions**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_document_chunks.py -v`

Expected: FAIL on import.

- [ ] **Step 3: Implement chunking, persistence and PostgreSQL index**

Chunk each page independently, max 4000 chars and 400 overlap. Persist SHA-256 of exact UTF-8 text. Before reinserting, delete chunks only for the same `documento_arquivo_id` inside one transaction.

Create the follow-up migration with `down_revision="b7d5e9f3a2c1"` and add the PostgreSQL index without editing the already-applied autos migration:

```python
op.execute(
    "create index if not exists ix_documento_trecho_fts "
    "on documento_trecho using gin (to_tsvector('portuguese', texto))"
)
```

`search_process_chunks` joins `DocumentoTrecho → DocumentoArquivo → Documento → Processo`, filters `escritorio_id` and `processo_id`, and on PostgreSQL ranks with `ts_rank_cd(to_tsvector('portuguese', texto), plainto_tsquery('portuguese', :query))`. SQLite tests use case-insensitive substring scoring. Return at most `limit=20` rows with document name, type, page and text.

- [ ] **Step 4: Run chunk/search tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_document_chunks.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/autos/chunks.py backend/tests/test_document_chunks.py backend/alembic/versions/c8e6f0a4b3d2_documento_trecho_fts.py
git commit -m "feat(autos): persist cited chunks with lexical search"
```

---

### Task 6: Resumo de cada documento com citações verificadas

**Files:**

- Create: `backend/app/autos/summarizer.py`
- Create: `backend/tests/test_document_summaries.py`
- Modify: `backend/app/settings.py`

**Interfaces:**

- Produces: `ChunkCitation`, `DocumentDigest`, `summarize_document`, `validate_citations`.

- [ ] **Step 1: Write tests that reject invented quotes**

```python
def test_summary_rejects_quote_not_present_in_chunk(db_session, document_with_chunks):
    digest = DocumentDigest(
        resumo="Resumo",
        fatos=[],
        pedidos=[],
        decisoes=[],
        prazos=[],
        incertezas=[],
        citations=[ChunkCitation(chunk_id=document_with_chunks[0].id, quote="FRASE INVENTADA")],
    )
    with pytest.raises(InvalidCitationError):
        validate_citations(db_session, digest)
```

- [ ] **Step 2: Run and verify missing summarizer**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_document_summaries.py -v`

Expected: FAIL on import.

- [ ] **Step 3: Implement structured digest and validation**

Pydantic schema:

```python
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
```

Use `get_provider(model=settings.claude_context_model)` with default `claude-haiku-4-5`. The prompt includes numbered chunks and requires every substantive item to reference a quote. `validate_citations` loads each chunk by ID, confirms it belongs to the target document version and checks normalized quote containment. Invalid output marks `DocumentoResumo.status="failed"`; it is never silently accepted.

- [ ] **Step 4: Run summary tests with fake provider**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_document_summaries.py -q`

Expected: PASS without external LLM calls.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/autos/summarizer.py backend/tests/test_document_summaries.py backend/app/settings.py
git commit -m "feat(autos): summarize every document with verified citations"
```

---

### Task 7: Construir o contexto integral e citado do processo

**Files:**

- Create: `backend/app/autos/context.py`
- Create: `backend/tests/test_process_context.py`
- Modify: `backend/app/agent/service.py`
- Modify: `backend/app/agent/drafter.py`
- Modify: `backend/tests/test_agent.py`
- Modify: `backend/tests/test_agent_service.py`

**Interfaces:**

- Produces: `ContextBundle`, `build_process_context`, `get_ready_context`.
- Replaces: `_historico_processo` as source principal; DataJud/DJEN remain supplementary chronology.

- [ ] **Step 1: Write a test requiring inventory coverage of every current file**

```python
def test_context_inventory_contains_every_verified_current_document(
    db_session, complete_extracted_process
):
    context = build_process_context(db_session, processo=complete_extracted_process)
    assert context.status == "ready"
    assert context.cobertura["documents_total"] == 3
    assert context.cobertura["documents_summarized"] == 3
    assert len(context.inventario) == 3
    assert all(item["documento_arquivo_id"] for item in context.inventario)
    assert context.citations
```

- [ ] **Step 2: Run and verify missing builder**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_process_context.py -v`

Expected: FAIL on import.

- [ ] **Step 3: Implement context readiness and prompt bundle**

`build_process_context` must:

1. Load the exact expected degree set recorded by the latest capture request (default `{1, 2}`) and require a `ProcessoInstancia` for each.
2. Require latest capture per instance to be `complete`; `not_applicable` is accepted only with evidence.
3. Load every current `DocumentoArquivo` in those manifests.
4. Require `extraction_status="complete"` and `DocumentoResumo.status="complete"` for each.
5. Compute `source_fingerprint = sha256("\n".join(sorted(source_parts)).encode("utf-8")).hexdigest()`, where `source_parts` contains every final manifest fingerprint and every current file SHA-256.
6. Persist inventory for 100% of files.
7. Assemble `contexto_consolidado` from metadata, DataJud movements, current intimation, every document digest and citation labels `[DOC-{documento_id} p.{page}]`.
8. Store `status="ready"`, coverage counts and citations.

Define:

```python
@dataclass(frozen=True)
class ContextBundle:
    contexto_id: int
    source_fingerprint: str
    inventory_text: str
    consolidated_text: str
    cited_excerpts: str
    citations: tuple[dict, ...]
```

`draft_from_intimacao` passes the bundle into `draft_peticao`; `drafter.py` instructs the model to cite document/page labels for factual statements. Keep deterministic deadline behavior unchanged. `Peticao.dossie` gains `contexto_id`, `source_fingerprint`, `inventario`, `citations`, `cobertura`.

- [ ] **Step 4: Run context and agent regressions**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_process_context.py tests/test_agent.py tests/test_agent_service.py -q
```

Expected: PASS; tests assert all document summaries appear in the input and no vault/session fields enter the prompt.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/autos/context.py backend/app/agent/service.py backend/app/agent/drafter.py backend/tests/test_process_context.py backend/tests/test_agent.py backend/tests/test_agent_service.py
git commit -m "feat(context): build complete cited process dossiers"
```

---

### Task 8: Gate fail-closed e override jurídico auditado

**Files:**

- Modify: `backend/app/autos/context.py`
- Modify: `backend/app/agent/service.py`
- Modify: `backend/app/queue/jobs.py`
- Modify: `backend/app/api/autos_routes.py`
- Modify: `backend/app/api/main.py`
- Modify: `backend/app/api/schemas.py`
- Create: `backend/tests/test_draft_context_gate.py`

**Interfaces:**

- Produces: `ContextNotReadyError`, `require_ready_context`, `create_context_override`, `consume_context_override`.
- API: `POST /processos/{id}/contexto/override` body `{action, justification}`.

- [ ] **Step 1: Write blocking and one-use override tests**

```python
def test_draft_is_blocked_without_ready_context(db_session, seeded_intimacao, calendar):
    with pytest.raises(ContextNotReadyError) as exc:
        draft_from_intimacao(db_session, seeded_intimacao, calendar=calendar)
    assert exc.value.code == "process_context_incomplete"


def test_lawyer_override_is_consumed_once(db_session, seeded_process, current_user):
    override = create_context_override(
        db_session,
        processo=seeded_process,
        usuario_id=current_user.usuario_id,
        action="draft",
        justification="Prazo fatal hoje; autos conferidos manualmente pelo advogado.",
    )
    assert consume_context_override(
        db_session, processo=seeded_process, usuario_id=current_user.usuario_id, action="draft"
    ).id == override.id
    assert consume_context_override(
        db_session, processo=seeded_process, usuario_id=current_user.usuario_id, action="draft"
    ) is None
```

- [ ] **Step 2: Run and verify gate failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_draft_context_gate.py -v`

Expected: FAIL because the gate does not exist.

- [ ] **Step 3: Implement the gate at draft and filing boundaries**

`require_ready_context` validates:

- latest `ContextoProcesso.status == "ready"`;
- current source fingerprint still matches latest captures/files;
- `ready_at` is not older than `settings.context_freshness_hours` (default 24), unless no court update occurred after it;
- otherwise consume a valid override for the exact action/user.

Create override with `expires_at=now+30min`, justification 20–1000 and audit action `process_context_override_created`. Consumption records `consumed_at` and audit action `process_context_override_consumed` including missing reasons.

Call the gate:

- before `draft_from_intimacao` invokes any LLM;
- before `run_pje_protocol_job` changes petition status to `protocolando`;
- verify the petition's stored source fingerprint still equals current context.

Map `ContextNotReadyError` to HTTP 409 with structured detail:

```json
{
  "code": "process_context_incomplete",
  "processo_id": 123,
  "missing": ["instancia:2", "documento:456:ocr_failed"]
}
```

- [ ] **Step 4: Update existing fixtures and run gate regressions**

Add `seed_ready_context(db_session, processo)` to `tests/conftest.py` and use it in tests that legitimately draft/file. Do not disable the gate globally in tests.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_draft_context_gate.py tests/test_agent_service.py tests/test_pje_vault_job.py tests/test_protocolo_roteado.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/autos/context.py backend/app/agent/service.py backend/app/queue/jobs.py backend/app/api/autos_routes.py backend/app/api/main.py backend/app/api/schemas.py backend/tests/conftest.py backend/tests/test_draft_context_gate.py backend/tests/test_agent_service.py backend/tests/test_pje_vault_job.py backend/tests/test_protocolo_roteado.py
git commit -m "feat(safety): fail closed on incomplete process context"
```

---

### Task 9: Estado de contexto no produto e operação manual

**Files:**

- Modify: `frontend/lib/api.ts`
- Create: `frontend/app/components/ProcessContextStatus.tsx`
- Create: `frontend/app/components/ProcessContextStatus.test.tsx`
- Modify: `frontend/app/views/ProcessosView.tsx`
- Modify: `docs/estado.md`
- Modify: `docs/operacao/go-live.md`

**Interfaces:**

- UI states: `not_captured`, `capturing`, `incomplete`, `processing`, `ready`, `stale`, `blocked`.
- Actions: `Capturar autos`, `Retentar pendências`, `Ver documentos`, `Liberar excepcionalmente`.

- [ ] **Step 1: Write UI test for an incomplete context**

```tsx
test("shows missing documents and keeps drafting blocked", async () => {
  render(<ProcessContextStatus processoId={7} />);
  expect(await screen.findByText("Contexto incompleto")).toBeInTheDocument();
  expect(screen.getByText(/2 documentos pendentes/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Gerar minuta" })).toBeDisabled();
});
```

- [ ] **Step 2: Run and verify missing component**

Run: `pnpm test -- ProcessContextStatus.test.tsx`

Expected: FAIL on import.

- [ ] **Step 3: Implement the status panel**

The panel shows per degree:

- system/court/degree;
- last capture time;
- expected/captured/missing counts;
- extraction/OCR/summarization counts;
- final fingerprint shortened to 12 characters;
- explicit reason for every block.

The override modal requires typed justification, displays a red warning that the generated piece may omit facts, and calls the one-use endpoint. Do not provide a permanent “do not warn again”.

- [ ] **Step 4: Run frontend and backend full verification**

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
cd ..\frontend
pnpm test
pnpm typecheck
pnpm build
```

Expected: all exit `0`.

- [ ] **Step 5: Commit**

```powershell
git add frontend/lib/api.ts frontend/app/components/ProcessContextStatus.tsx frontend/app/components/ProcessContextStatus.test.tsx frontend/app/views/ProcessosView.tsx docs/estado.md docs/operacao/go-live.md
git commit -m "feat(frontend): expose complete process-context status and gate"
```

## Core context acceptance gate

- [ ] Initial/final manifest equality is mandatory.
- [ ] Every manifest item points to a verified immutable file version.
- [ ] Every PDF page has native text or OCR; empty page is an explicit failure.
- [ ] Every current file has a valid structured summary.
- [ ] Every summary citation is verified against a persisted chunk.
- [ ] Context inventory contains 100% of current files from all required instances.
- [ ] Draft/file calls fail before LLM/browser when context is incomplete or stale.
- [ ] Override is short-lived, one-use and audited.
- [ ] Full backend/frontend suite is green before claiming Marco B.

---

### Task 10: Download privado, retenção e descarte auditado

**Files:**

- Modify: `backend/app/storage/objects.py`
- Modify: `backend/app/api/autos_routes.py`
- Modify: `backend/app/autos/worker.py`
- Modify: `backend/app/cli.py`
- Create: `backend/tests/test_document_access.py`
- Modify: `docs/operacao/go-live.md`

**Interfaces:**

- User API: `POST /documentos/{id}/download-ticket` returns a 300-second private URL.
- Admin/service API: process/tenant deletion enqueues `purge_process_objects`; no request deletes thousands of objects synchronously.

- [ ] **Step 1: Write cross-tenant and retention tests**

```python
def test_other_tenant_cannot_get_document_download_ticket(client, other_tenant_document):
    response = client.post(f"/documentos/{other_tenant_document.id}/download-ticket")
    assert response.status_code == 404


def test_process_delete_enqueues_object_purge(db_session, owned_process_with_files):
    enqueue_process_purge(db_session, processo=owned_process_with_files, actor="usuario:1")
    job = db_session.query(models.JobExecucao).filter_by(tipo="purge_process_objects").one()
    assert job.payload == {"processo_id": owned_process_with_files.id}
```

- [ ] **Step 2: Run and verify missing access contract**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_document_access.py -v`

Expected: FAIL because signed download and purge jobs do not exist.

- [ ] **Step 3: Implement private access and explicit retention**

Add `ObjectStore.create_download_ticket(key, expires_in=300)`. S3 uses `generate_presigned_url("get_object", ...)`; localdev returns an authenticated API URL, never a filesystem path. The endpoint resolves `Documento → Processo.escritorio_id`, returns 404 across tenants, records `document_download_ticket_created` without storing the signed URL, and exposes only `url`, `expires_in`, `nome`, `mime_type`.

Object keys are immutable and include `tenant/{escritorio_id}/process/{processo_id}/instance/{instancia_id}/document/{documento_id}/{sha256}.bin`; a new file version never overwrites the previous key. Automatic age-based deletion is disabled. Explicit process/tenant deletion enqueues a purge job, lists keys from DB, deletes in bounded batches of 100, records counts/hashes in audit and only then deletes metadata according to the existing tenant cleanup order.

- [ ] **Step 4: Run security and complete plan verification**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_document_access.py tests/test_autos_service.py tests/test_draft_context_gate.py -q
.\.venv\Scripts\python.exe -m ruff check app tests
```

Expected: PASS; no response exposes bucket credentials, raw private URI or cross-tenant existence.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/storage/objects.py backend/app/api/autos_routes.py backend/app/autos/worker.py backend/app/cli.py backend/tests/test_document_access.py docs/operacao/go-live.md
git commit -m "feat(autos): secure document access retention and purge"
```

## Final Plan 2 acceptance gate

- [ ] Binary capture, extraction, summaries and context have separate observable states.
- [ ] OCR/LLM work runs outside request transactions with bounded concurrency and retry.
- [ ] Large downloads stream to temporary files and respect the configured size ceiling.
- [ ] Documents are private, tenant-scoped and served only by short signed tickets.
- [ ] File versions use immutable keys because Supabase S3 does not provide object versioning.
- [ ] Destruction is explicit, batched and audited; there is no silent retention expiry.
