# Fundação de automação judicial e agente local — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar os contratos, dados, storage privado e agente Windows necessários para executar leitura e protocolo autenticados na máquina do advogado, sem enviar sessões ou certificados ao backend.

**Architecture:** O backend publica comandos idempotentes vinculados a `ProcessoInstancia`; o agente local autenticado reivindica um comando, usa um perfil Playwright persistente e devolve somente resultado/evidência. Arquivos seguem direto para storage privado por URL S3 pré-assinada e são confirmados no backend. A implementação mantém o fluxo PJe legado em sandbox até o Plano 3 migrá-lo.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy/Alembic, PostgreSQL/SQLite em testes, Playwright, keyring do Windows, boto3, S3/Supabase Storage, Next.js/TypeScript.

## Global Constraints

- Nenhum segredo de tribunal entra em `AgentCommand.payload`, `resultado`, `AuditLog` ou prompt.
- Tokens de agente são exibidos uma vez, persistidos somente como SHA-256 no backend e revogáveis.
- Código de pareamento expira em 10 minutos e só pode ser consumido uma vez.
- Perfis Playwright ficam em `%LOCALAPPDATA%\Causor\profiles` e nunca entram no Git.
- Um processo pode ter várias instâncias; não adicionar `grau` diretamente em `Processo`.
- `AgentCommand.idempotency_key` é única por escritório.
- Claim de comando usa lock/compare-and-set; dois agentes não executam o mesmo comando.
- Upload S3 usa URL pré-assinada de 15 minutos e bucket privado.
- O backend recomputa hash ao ingerir; `x-amz-meta-sha256` informado pelo agente não é prova suficiente.
- `CAUSOR_FILING_MODE=sandbox` permanece default.

---

## File map

**Create**

- `backend/app/connectors/contracts.py` — tipos neutros de sistema para leitura e protocolo.
- `backend/app/agent_runtime/models.py` — DTOs de comandos/resultados do agente.
- `backend/app/agent_runtime/auth.py` — pareamento, hashing e autenticação do agente.
- `backend/app/agent_runtime/service.py` — criação, claim, heartbeat e conclusão idempotente.
- `backend/app/api/agent_routes.py` — endpoints do agente e do usuário autenticado.
- `backend/app/storage/objects.py` — `ObjectStore`, local e S3, mais presigned upload.
- `backend/app/local_agent/config.py` — configuração local não secreta + keyring.
- `backend/app/local_agent/browser.py` — perfis Playwright persistentes.
- `backend/app/local_agent/client.py` — cliente HTTP do protocolo do agente.
- `backend/app/local_agent/worker.py` — loop de claim/dispatch/heartbeat.
- `backend/app/local_agent/__main__.py` — CLI `pair`, `login` e `run`.
- `backend/alembic/versions/a6c4d8e2f1b0_agent_runtime_processo_instancia.py` — schema da fundação.
- `backend/tests/test_connector_contracts.py`
- `backend/tests/test_object_store.py`
- `backend/tests/test_agent_auth.py`
- `backend/tests/test_agent_commands.py`
- `backend/tests/test_agent_api.py`
- `backend/tests/test_local_agent.py`
- `frontend/app/components/AgentSection.tsx`
- `frontend/app/components/AgentSection.test.tsx`

**Modify**

- `backend/app/sor/models.py` — `ProcessoInstancia`, instalações, pairing codes e comandos.
- `backend/app/sor/__init__.py` — expor modelos se necessário pelo padrão atual.
- `backend/app/settings.py` — parâmetros do storage e agente.
- `backend/app/api/main.py` — incluir `agent_routes.router`.
- `backend/pyproject.toml` — `boto3`, `keyring`.
- `backend/.env.example` — configuração S3/Supabase privada.
- `backend/.gitignore` e `.gitignore` — perfis, traces e uploads locais.
- `frontend/lib/api.ts` — API de pareamento/status.
- `frontend/app/SettingsModal.tsx` — renderizar `AgentSection`.
- `docs/operacao/go-live.md` — substituir o paliativo pelo agente local.

---

### Task 1: Contratos neutros de sistema judicial

**Files:**

- Create: `backend/app/connectors/contracts.py`
- Create: `backend/tests/test_connector_contracts.py`
- Modify: `backend/app/connectors/drivers.py`

**Interfaces:**

- Produces: `CourtTarget`, `CourtDocumentRef`, `CourtManifestSnapshot`, `FilingPackage`, `FilingCheckpoint`, `CourtReaderDriver`, `FilingDriver`.
- Consumes: nenhum tipo PJe; os tipos não podem importar módulos sob `connectors/pje`.

- [ ] **Step 1: Write the failing contract tests**

```python
# backend/tests/test_connector_contracts.py
from datetime import datetime, timezone

from app.connectors.contracts import (
    CourtDocumentRef,
    CourtManifestSnapshot,
    CourtTarget,
    FilingCheckpoint,
    FilingPackage,
)


def test_contracts_are_system_neutral_and_serializable():
    target = CourtTarget(
        processo_instancia_id=7,
        processo_id=3,
        numero_processo="00000010020248260100",
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_base="https://pje.tjmg.jus.br/pje",
    )
    ref = CourtDocumentRef(
        external_id="doc-1",
        nome="Decisão.pdf",
        tipo="Decisão",
        ordem=1,
        data_documento=None,
        sigiloso=False,
        mime_type="application/pdf",
        size_hint=None,
        download_ref="opaque:doc-1",
    )
    snapshot = CourtManifestSnapshot(
        target=target,
        documentos=(ref,),
        cursor_complete=True,
        source_fingerprint="sha256:abc",
        captured_at=datetime.now(timezone.utc),
        evidence={},
    )
    package = FilingPackage(
        peticao_id=9,
        processo_instancia_id=7,
        numero_processo=target.numero_processo,
        tribunal=target.tribunal,
        sistema=target.sistema,
        grau=target.grau,
        tipo_peticao="Manifestação",
        pdf_bytes=b"%PDF-1.4\n%%EOF\n",
    )
    checkpoint = FilingCheckpoint(
        checkpoint="ready_to_sign",
        modo="local_agent",
        irreversible=False,
        evidence={"states": ["minuta_anexada"]},
    )

    assert snapshot.documentos[0].external_id == "doc-1"
    assert package.sistema == "PJe"
    assert checkpoint.irreversible is False
```

- [ ] **Step 2: Run the test and verify the missing module failure**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_connector_contracts.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.connectors.contracts'`.

- [ ] **Step 3: Implement the contracts exactly**

```python
# backend/app/connectors/contracts.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class CourtTarget:
    processo_instancia_id: int
    processo_id: int
    numero_processo: str
    sistema: str
    tribunal: str
    grau: str
    url_base: str


@dataclass(frozen=True)
class CourtDocumentRef:
    external_id: str
    nome: str
    tipo: str | None
    ordem: int
    data_documento: date | None
    sigiloso: bool
    mime_type: str | None
    size_hint: int | None
    download_ref: str
    parent_external_id: str | None = None


@dataclass(frozen=True)
class CourtManifestSnapshot:
    target: CourtTarget
    documentos: tuple[CourtDocumentRef, ...]
    cursor_complete: bool
    source_fingerprint: str
    captured_at: datetime
    evidence: dict


@dataclass(frozen=True)
class FilingPackage:
    peticao_id: int
    processo_instancia_id: int
    numero_processo: str
    tribunal: str
    sistema: str
    grau: str
    tipo_peticao: str | None
    pdf_bytes: bytes


@dataclass(frozen=True)
class FilingCheckpoint:
    checkpoint: str
    modo: str
    irreversible: bool
    evidence: dict


class CourtReaderDriver(Protocol):
    sistema: str

    def enumerate_documents(self, target: CourtTarget) -> CourtManifestSnapshot: ...

    def download_document(self, target: CourtTarget, ref: CourtDocumentRef) -> bytes: ...


class FilingDriver(Protocol):
    sistema: str

    def prepare_filing(
        self, package: FilingPackage, *, submit: bool = False
    ) -> FilingCheckpoint: ...
```

Em `backend/app/connectors/drivers.py`, remova a definição local de `FilingDriver` e importe-a de `contracts`. Preserve temporariamente `PjeDriver` e o adapter legado; o Plano 3 remove os tipos `PjeFiling*`.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_connector_contracts.py tests/test_filing_drivers.py tests/test_pje_connector.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/connectors/contracts.py backend/app/connectors/drivers.py backend/tests/test_connector_contracts.py
git commit -m "refactor(connectors): add system-neutral court contracts"
```

---

### Task 2: Modelar instâncias, instalações e comandos do agente

**Files:**

- Modify: `backend/app/sor/models.py`
- Create: `backend/alembic/versions/a6c4d8e2f1b0_agent_runtime_processo_instancia.py`
- Create: `backend/tests/test_agent_models.py`

**Interfaces:**

- Produces: `ProcessoInstancia`, `AgentInstallation`, `AgentPairingCode`, `AgentCommand`.
- Constraint: `ProcessoInstancia` é única por `(processo_id, sistema, tribunal, grau)`.
- Constraint: `AgentCommand` é única por `(escritorio_id, idempotency_key)`.

- [ ] **Step 1: Write failing model tests**

```python
# backend/tests/test_agent_models.py
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
import pytest

from app.sor import models


def test_process_can_have_first_and_second_degree_instances(db_session, seeded):
    first = models.ProcessoInstancia(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_base="https://pje.tjmg.jus.br/pje",
        status="active",
    )
    second = models.ProcessoInstancia(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="2",
        url_base="https://pje2g.tjmg.jus.br/pje",
        status="active",
    )
    db_session.add_all([first, second])
    db_session.flush()
    assert {item.grau for item in seeded.instancias} == {"1", "2"}


def test_agent_command_idempotency_is_tenant_scoped(db_session, seeded):
    command = dict(
        escritorio_id=seeded.escritorio_id,
        usuario_id=None,
        installation_id=None,
        tipo="read_process",
        status="queued",
        idempotency_key="capture:1:manifest:1",
        payload={"processo_instancia_id": 1},
    )
    db_session.add(models.AgentCommand(**command))
    db_session.flush()
    db_session.add(models.AgentCommand(**command))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_pairing_code_has_expiry_and_single_use_fields(db_session, seeded):
    usuario = db_session.query(models.Usuario).first()
    code = models.AgentPairingCode(
        escritorio_id=seeded.escritorio_id,
        usuario_id=usuario.id,
        code_hash="a" * 64,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db_session.add(code)
    db_session.flush()
    assert code.used_at is None
```

- [ ] **Step 2: Run tests and verify missing models**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_agent_models.py -v`

Expected: FAIL because the four models do not exist.

- [ ] **Step 3: Add the exact model fields**

Add to `backend/app/sor/models.py`:

```python
class ProcessoInstancia(TimestampMixin, Base):
    __tablename__ = "processo_instancia"
    __table_args__ = (
        UniqueConstraint(
            "processo_id", "sistema", "tribunal", "grau",
            name="uq_processo_instancia_route",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processo.id"), nullable=False)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorio.id"), nullable=False, index=True)
    sistema: Mapped[str] = mapped_column(String(20), nullable=False)
    tribunal: Mapped[str] = mapped_column(String(50), nullable=False)
    grau: Mapped[str] = mapped_column(String(4), nullable=False)
    url_base: Mapped[str | None] = mapped_column(String(1024))
    external_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")

    processo: Mapped[Processo] = relationship(back_populates="instancias")


class AgentInstallation(TimestampMixin, Base):
    __tablename__ = "agent_installation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorio.id"), nullable=False, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[str | None] = mapped_column(String(40))


class AgentPairingCode(TimestampMixin, Base):
    __tablename__ = "agent_pairing_code"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorio.id"), nullable=False, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentCommand(TimestampMixin, Base):
    __tablename__ = "agent_command"
    __table_args__ = (
        UniqueConstraint("escritorio_id", "idempotency_key", name="uq_agent_command_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorio.id"), nullable=False, index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    installation_id: Mapped[int | None] = mapped_column(ForeignKey("agent_installation.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    resultado: Mapped[dict | None] = mapped_column(JSON)
    erro_codigo: Mapped[str | None] = mapped_column(String(80))
    erro_detalhe: Mapped[str | None] = mapped_column(Text)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Add to `Processo`:

```python
instancias: Mapped[list[ProcessoInstancia]] = relationship(
    back_populates="processo", cascade="all, delete-orphan"
)
```

Create the Alembic migration with the same columns, foreign keys, unique constraints and indexes. Its downgrade order is: indexes → unique constraints/tables via `op.drop_table` → no changes to `processo` because the relationship is ORM-only.

- [ ] **Step 4: Run migration/model tests**

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m pytest tests/test_agent_models.py tests/test_court_routing.py -q
```

Expected: PASS; `alembic current` reports `a6c4d8e2f1b0`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/sor/models.py backend/alembic/versions/a6c4d8e2f1b0_agent_runtime_processo_instancia.py backend/tests/test_agent_models.py
git commit -m "feat(agent): model process instances and local-agent commands"
```

---

### Task 3: Storage privado local/S3 e upload pré-assinado

**Files:**

- Modify: `backend/pyproject.toml`
- Modify: `backend/app/settings.py`
- Modify: `backend/.env.example`
- Create: `backend/app/storage/__init__.py`
- Create: `backend/app/storage/objects.py`
- Create: `backend/tests/test_object_store.py`

**Interfaces:**

- Produces: `StoredObject`, `UploadTicket`, `ObjectStore`, `LocalObjectStore`, `S3ObjectStore`, `get_object_store()`.
- `create_upload_ticket(key, content_type, sha256, size_bytes)` returns URL/headers valid for 900 seconds.

- [ ] **Step 1: Write failing tests for local storage and safe keys**

```python
# backend/tests/test_object_store.py
from hashlib import sha256

import pytest

from app.storage.objects import LocalObjectStore, UnsafeObjectKeyError


def test_local_store_round_trip_and_hash(tmp_path):
    store = LocalObjectStore(tmp_path)
    data = b"%PDF-1.4\n%%EOF\n"
    stored = store.put_bytes("tenant/1/process/2/doc.pdf", data, "application/pdf")
    assert stored.sha256 == sha256(data).hexdigest()
    assert store.get_bytes(stored.key) == data


@pytest.mark.parametrize("key", ["../secret", "/absolute", "tenant\\escape"])
def test_local_store_rejects_unsafe_key(tmp_path, key):
    store = LocalObjectStore(tmp_path)
    with pytest.raises(UnsafeObjectKeyError):
        store.put_bytes(key, b"x", "application/octet-stream")
```

- [ ] **Step 2: Add dependencies and run the failing test**

Add to `backend/pyproject.toml` dependencies:

```toml
"boto3>=1.35",
"keyring>=25.0",
```

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_object_store.py -v`

Expected: FAIL because `app.storage.objects` does not exist.

- [ ] **Step 3: Implement the store contracts**

`backend/app/storage/objects.py` must define:

```python
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256 as sha256_digest
from pathlib import Path, PurePosixPath
from typing import Protocol
import boto3

from app.settings import settings


class UnsafeObjectKeyError(ValueError):
    pass


@dataclass(frozen=True)
class StoredObject:
    key: str
    uri: str
    size_bytes: int
    sha256: str
    content_type: str


@dataclass(frozen=True)
class UploadTicket:
    key: str
    method: str
    url: str
    headers: dict[str, str]
    expires_in: int


class ObjectStore(Protocol):
    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject: ...
    def get_bytes(self, key: str) -> bytes: ...
    def download_to(self, key: str, destination: Path) -> None: ...
    def create_upload_ticket(
        self, key: str, content_type: str, sha256: str, size_bytes: int
    ) -> UploadTicket: ...


def _safe_key(key: str) -> str:
    path = PurePosixPath(key)
    if path.is_absolute() or ".." in path.parts or "\\" in key or not key.strip():
        raise UnsafeObjectKeyError("unsafe object key")
    return str(path)


class LocalObjectStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        safe = _safe_key(key)
        target = (self.root / safe).resolve()
        if self.root not in target.parents:
            raise UnsafeObjectKeyError("object escaped storage root")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        digest = sha256_digest(data).hexdigest()
        return StoredObject(safe, f"local-object://{safe}", len(data), digest, content_type)

    def get_bytes(self, key: str) -> bytes:
        safe = _safe_key(key)
        return (self.root / safe).read_bytes()

    def download_to(self, key: str, destination: Path) -> None:
        safe = _safe_key(key)
        destination.write_bytes((self.root / safe).read_bytes())

    def create_upload_ticket(
        self, key: str, content_type: str, sha256: str, size_bytes: int
    ) -> UploadTicket:
        safe = _safe_key(key)
        return UploadTicket(
            key=safe,
            method="PUT",
            url=f"local-object://{safe}",
            headers={
                "content-type": content_type,
                "x-causor-sha256": sha256,
                "x-causor-size": str(size_bytes),
            },
            expires_in=900,
        )


class S3ObjectStore:
    def __init__(self):
        self.bucket = settings.object_store_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.object_store_endpoint or None,
            region_name=settings.object_store_region,
            aws_access_key_id=settings.object_store_access_key,
            aws_secret_access_key=settings.object_store_secret_key,
        )

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        safe = _safe_key(key)
        digest = sha256_digest(data).hexdigest()
        self.client.put_object(
            Bucket=self.bucket,
            Key=safe,
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": digest},
        )
        return StoredObject(safe, f"s3://{self.bucket}/{safe}", len(data), digest, content_type)

    def get_bytes(self, key: str) -> bytes:
        safe = _safe_key(key)
        response = self.client.get_object(Bucket=self.bucket, Key=safe)
        return response["Body"].read()

    def download_to(self, key: str, destination: Path) -> None:
        safe = _safe_key(key)
        self.client.download_file(self.bucket, safe, str(destination))

    def create_upload_ticket(
        self, key: str, content_type: str, sha256: str, size_bytes: int
    ) -> UploadTicket:
        safe = _safe_key(key)
        params = {
            "Bucket": self.bucket,
            "Key": safe,
            "ContentType": content_type,
            "Metadata": {"sha256": sha256, "size": str(size_bytes)},
        }
        url = self.client.generate_presigned_url(
            "put_object", Params=params, ExpiresIn=900, HttpMethod="PUT"
        )
        return UploadTicket(
            key=safe,
            method="PUT",
            url=url,
            headers={
                "content-type": content_type,
                "x-amz-meta-sha256": sha256,
                "x-amz-meta-size": str(size_bytes),
            },
            expires_in=900,
        )


def get_object_store() -> ObjectStore:
    if settings.object_store_provider == "localdev":
        return LocalObjectStore(settings.object_store_local_path)
    if settings.object_store_provider == "s3":
        return S3ObjectStore()
    raise ValueError(f"unknown object store provider: {settings.object_store_provider}")
```

Add settings:

```python
object_store_provider: str = "localdev"
object_store_local_path: str = "./artifacts/objects"
object_store_endpoint: str = ""
object_store_region: str = "sa-east-1"
object_store_bucket: str = "causor-process-documents"
object_store_access_key: str = ""
object_store_secret_key: str = ""
```

Document matching `CAUSOR_OBJECT_STORE_*` variables in `.env.example`; never commit access/secret keys.

- [ ] **Step 4: Run tests and install editable dependencies if needed**

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests/test_object_store.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/pyproject.toml backend/app/settings.py backend/.env.example backend/app/storage backend/tests/test_object_store.py
git commit -m "feat(storage): add private local and S3 object stores"
```

---

### Task 4: Pareamento e autenticação revogável do agente

**Files:**

- Create: `backend/app/agent_runtime/__init__.py`
- Create: `backend/app/agent_runtime/models.py`
- Create: `backend/app/agent_runtime/auth.py`
- Create: `backend/tests/test_agent_auth.py`

**Interfaces:**

- Produces: `PairingSecret`, `AgentPrincipal`, `create_pairing_code`, `consume_pairing_code`, `authenticate_agent`.
- Headers do agente: `Authorization: Agent <token>`.

- [ ] **Step 1: Write failing auth tests**

```python
# backend/tests/test_agent_auth.py
from app.agent_runtime.auth import (
    AgentAuthError,
    authenticate_agent_token,
    consume_pairing_code,
    create_pairing_code,
)
from app.sor import models


def test_pairing_code_is_single_use(db_session, seeded):
    usuario = db_session.query(models.Usuario).first()
    secret = create_pairing_code(db_session, usuario=usuario)
    installation, token = consume_pairing_code(
        db_session, code=secret.code, installation_name="Notebook jurídico", version="0.1.0"
    )
    assert token
    assert authenticate_agent_token(db_session, token).id == installation.id

    try:
        consume_pairing_code(
            db_session, code=secret.code, installation_name="Reuso", version="0.1.0"
        )
    except AgentAuthError as exc:
        assert "used" in str(exc)
    else:
        raise AssertionError("pairing code was reused")
```

- [ ] **Step 2: Run and verify failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_agent_auth.py -v`

Expected: FAIL because `agent_runtime.auth` does not exist.

- [ ] **Step 3: Implement hash-only tokens and expiry**

```python
# backend/app/agent_runtime/auth.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.sor import models


class AgentAuthError(ValueError):
    pass


@dataclass(frozen=True)
class PairingSecret:
    code: str
    expires_at: datetime


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_pairing_code(session: Session, *, usuario: models.Usuario) -> PairingSecret:
    raw = secrets.token_urlsafe(24)
    expires_at = _now() + timedelta(minutes=10)
    session.add(
        models.AgentPairingCode(
            escritorio_id=usuario.escritorio_id,
            usuario_id=usuario.id,
            code_hash=_digest(raw),
            expires_at=expires_at,
        )
    )
    session.flush()
    return PairingSecret(code=raw, expires_at=expires_at)


def consume_pairing_code(
    session: Session, *, code: str, installation_name: str, version: str
) -> tuple[models.AgentInstallation, str]:
    row = session.scalars(
        select(models.AgentPairingCode).where(models.AgentPairingCode.code_hash == _digest(code))
    ).first()
    now = _now()
    if row is None:
        raise AgentAuthError("invalid pairing code")
    if row.used_at is not None:
        raise AgentAuthError("pairing code already used")
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise AgentAuthError("pairing code expired")

    raw_token = secrets.token_urlsafe(32)
    installation = models.AgentInstallation(
        escritorio_id=row.escritorio_id,
        usuario_id=row.usuario_id,
        nome=installation_name,
        token_hash=_digest(raw_token),
        ativo=True,
        version=version,
        last_seen_at=now,
    )
    row.used_at = now
    session.add(installation)
    session.flush()
    return installation, raw_token


def authenticate_agent_token(session: Session, token: str) -> models.AgentInstallation:
    installation = session.scalars(
        select(models.AgentInstallation).where(
            models.AgentInstallation.token_hash == _digest(token),
            models.AgentInstallation.ativo.is_(True),
        )
    ).first()
    if installation is None:
        raise AgentAuthError("invalid agent token")
    installation.last_seen_at = _now()
    return installation
```

- [ ] **Step 4: Run auth tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_agent_auth.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/agent_runtime backend/tests/test_agent_auth.py
git commit -m "feat(agent): add one-time pairing and revocable tokens"
```

---

### Task 5: Serviço idempotente de comandos e API do agente

**Files:**

- Create: `backend/app/agent_runtime/service.py`
- Create: `backend/app/api/agent_routes.py`
- Modify: `backend/app/api/main.py`
- Create: `backend/tests/test_agent_commands.py`
- Create: `backend/tests/test_agent_api.py`

**Interfaces:**

- Produces: `enqueue_command`, `claim_next_command`, `heartbeat_command`, `complete_command`, `fail_command`.
- API usuário: `POST /agent/pairing-codes`, `GET /agent/installations`, `DELETE /agent/installations/{id}`.
- API agente: `POST /agent/pair`, `POST /agent/commands/claim`, `POST /agent/commands/{id}/heartbeat`, `POST /agent/commands/{id}/complete`, `POST /agent/commands/{id}/fail`.
- Upload localdev: `PUT /agent/uploads/local?key=tenant/{escritorio_id}/...` com corpo binário, autenticação do agente, limite configurável e conferência de hash/tamanho.

- [ ] **Step 1: Write service tests for idempotency and ownership**

```python
# backend/tests/test_agent_commands.py
from app.agent_runtime.service import claim_next_command, complete_command, enqueue_command
from app.sor import models


def test_command_is_enqueued_once_and_claimed_once(db_session, seeded):
    usuario = db_session.query(models.Usuario).first()
    installation = models.AgentInstallation(
        escritorio_id=seeded.escritorio_id,
        usuario_id=usuario.id,
        nome="Agent",
        token_hash="b" * 64,
        ativo=True,
    )
    db_session.add(installation)
    db_session.flush()

    first = enqueue_command(
        db_session,
        escritorio_id=seeded.escritorio_id,
        usuario_id=usuario.id,
        tipo="read_process",
        idempotency_key="read:instance:1:generation:1",
        payload={"processo_instancia_id": 1},
    )
    second = enqueue_command(
        db_session,
        escritorio_id=seeded.escritorio_id,
        usuario_id=usuario.id,
        tipo="read_process",
        idempotency_key="read:instance:1:generation:1",
        payload={"processo_instancia_id": 1},
    )
    assert first.id == second.id

    claimed = claim_next_command(db_session, installation=installation)
    assert claimed.id == first.id
    assert claim_next_command(db_session, installation=installation) is None

    complete_command(
        db_session,
        command=claimed,
        installation=installation,
        resultado={"status": "complete"},
    )
    assert claimed.status == "completed"
```

- [ ] **Step 2: Run and verify missing service**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_agent_commands.py -v`

Expected: FAIL on import.

- [ ] **Step 3: Implement transitions and routes**

The service must enforce this state machine:

```python
_TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": {"completed", "failed", "queued"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}
```

`enqueue_command` first queries `(escritorio_id, idempotency_key)` and returns the existing row. `claim_next_command` selects the oldest `queued` command for the same office using `with_for_update(skip_locked=True)`, assigns `installation_id`, sets `running`, `claimed_at` and `heartbeat_at`. Completion/failure verifies `command.installation_id == installation.id`; otherwise raises `AgentCommandOwnershipError`.

Agent authentication dependency in `agent_routes.py`:

```python
def get_agent_principal(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> models.AgentInstallation:
    if not authorization or not authorization.startswith("Agent "):
        raise HTTPException(status_code=401, detail="agent authentication required")
    try:
        return authenticate_agent_token(session, authorization.removeprefix("Agent ").strip())
    except AgentAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
```

Use Pydantic request/response models in the same file; `CommandOut` exposes `id`, `tipo`, `payload`, `status`, never `token_hash`. Include the router in `create_app()`:

```python
from app.api.agent_routes import router as agent_router

app.include_router(agent_router)
```

The localdev upload route reads the raw request body (no multipart dependency), requires the object key prefix `tenant/{installation.escritorio_id}/`, rejects bodies above `settings.agent_max_upload_bytes`, compares `x-causor-size` and `x-causor-sha256`, and only then calls `LocalObjectStore.put_bytes`. Plan 2 additionally binds the key to an active capture/document ticket.

- [ ] **Step 4: Run service and API tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agent_commands.py tests/test_agent_api.py -q
```

Expected: PASS, including 401 without agent token, 404 across tenants and idempotent completion.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/agent_runtime/service.py backend/app/api/agent_routes.py backend/app/api/main.py backend/tests/test_agent_commands.py backend/tests/test_agent_api.py
git commit -m "feat(agent): add idempotent command protocol and API"
```

---

### Task 6: Agente Windows com keyring e perfil Playwright persistente

**Files:**

- Create: `backend/app/local_agent/config.py`
- Create: `backend/app/local_agent/client.py`
- Create: `backend/app/local_agent/browser.py`
- Create: `backend/app/local_agent/worker.py`
- Create: `backend/app/local_agent/__main__.py`
- Create: `backend/tests/test_local_agent.py`
- Modify: `.gitignore`

**Interfaces:**

- CLI: `python -m app.local_agent pair --api URL --code CODE --name NAME`.
- CLI: `python -m app.local_agent login --system PJe --court TJMG --degree 1 --url URL`.
- CLI: `python -m app.local_agent run`.
- Produces: `profile_dir(system, tribunal, grau)`, `AgentApiClient`, `AgentWorker`.

- [ ] **Step 1: Write tests for deterministic profile paths and keyring token use**

```python
# backend/tests/test_local_agent.py
from pathlib import Path

from app.local_agent.browser import profile_dir


def test_profile_path_is_scoped_by_system_court_and_degree(tmp_path):
    first = profile_dir(tmp_path, "PJe", "TJMG", "1")
    second = profile_dir(tmp_path, "PJe", "TJMG", "2")
    assert first != second
    assert first == tmp_path / "pje" / "tjmg" / "1"
    assert ".." not in first.parts
```

- [ ] **Step 2: Run and verify missing local-agent package**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_local_agent.py -v`

Expected: FAIL on import.

- [ ] **Step 3: Implement local configuration and persistent browser**

`config.py` stores only API URL, installation ID and name as JSON under `%LOCALAPPDATA%\Causor\agent.json`. Store the agent token with:

```python
keyring.set_password("causor-agent", str(installation_id), token)
```

`browser.py`:

```python
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import re

from playwright.sync_api import sync_playwright


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")


def profile_dir(root: Path, sistema: str, tribunal: str, grau: str) -> Path:
    if grau not in {"1", "2"}:
        raise ValueError("grau must be 1 or 2")
    return root / _slug(sistema) / _slug(tribunal) / grau


@contextmanager
def persistent_court_context(
    *, root: Path, sistema: str, tribunal: str, grau: str, url: str, headed: bool = True
):
    directory = profile_dir(root, sistema, tribunal, grau)
    directory.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(directory),
            headless=not headed,
            accept_downloads=True,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        try:
            yield context, page
        finally:
            context.close()
```

`AgentApiClient` uses `httpx.Client`, sends `Authorization: Agent <token>`, has `claim()`, `heartbeat(id)`, `complete(id, result)` and `fail(id, code, detail)`. It never logs headers or response bodies containing tokens.

When an upload ticket uses `local-object://`, `AgentApiClient.upload()` sends the bytes to authenticated `PUT /agent/uploads/local` with `key`, declared hash and size headers; the route calls `LocalObjectStore.put_bytes` and verifies office ownership from the active capture. For `https://` tickets, it performs the presigned S3 `PUT` directly with exactly the returned headers. This makes local development executable without inventing an unpersisted ticket token.

`AgentWorker.run_once()` claims one command and dispatches by `tipo`; until Plans 2/3 register handlers, an unknown kind fails with `unsupported_command`. Heartbeat runs every 20 seconds while a handler executes.

Add to `.gitignore`:

```gitignore
backend/artifacts/
playwright/.auth/
*.zip.trace
```

- [ ] **Step 4: Run tests and CLI help**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_local_agent.py -q
.\.venv\Scripts\python.exe -m app.local_agent --help
```

Expected: PASS; help lists `pair`, `login`, `run`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/local_agent backend/tests/test_local_agent.py .gitignore
git commit -m "feat(agent): add Windows worker with persistent court profiles"
```

---

### Task 7: Tela de pareamento e estado do agente

**Files:**

- Modify: `frontend/lib/api.ts`
- Create: `frontend/app/components/AgentSection.tsx`
- Create: `frontend/app/components/AgentSection.test.tsx`
- Modify: `frontend/app/SettingsModal.tsx`

**Interfaces:**

- Produces TS types: `AgentInstallation`, `AgentPairingCode`.
- API functions: `listarAgentes`, `criarCodigoPareamento`, `revogarAgente`.

- [ ] **Step 1: Write component test**

```tsx
// frontend/app/components/AgentSection.test.tsx
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import AgentSection from "./AgentSection";

vi.mock("@/lib/api", () => ({
  listarAgentes: vi.fn().mockResolvedValue([
    { id: 1, nome: "Notebook jurídico", ativo: true, last_seen_at: "2026-07-10T12:00:00Z", version: "0.1.0" }
  ]),
  criarCodigoPareamento: vi.fn(),
  revogarAgente: vi.fn()
}));

test("shows paired agent health", async () => {
  render(<AgentSection offline={false} />);
  expect(await screen.findByText("Notebook jurídico")).toBeInTheDocument();
  expect(screen.getByText(/0.1.0/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run and verify missing component**

Run:

```powershell
cd frontend
pnpm test -- AgentSection.test.tsx
```

Expected: FAIL because `AgentSection` does not exist.

- [ ] **Step 3: Implement API and component behavior**

`AgentSection` must render:

- status `Online` when `last_seen_at` is at most 90 seconds old;
- status `Offline` otherwise;
- button `Parear este computador`, which requests a code and displays the exact command built from the runtime API base and returned one-time code: `python -m app.local_agent pair --api ${API_BASE} --code ${PAIRING_CODE} --name "Meu computador"`;
- code expiration timestamp;
- revocation button with confirmation;
- no token, cookie or storage state.

Add `<AgentSection offline={offline} />` immediately before `VaultSection` in `SettingsModal`. Keep `VaultSection` during migration; Plan 3 removes server-side session capture.

- [ ] **Step 4: Run frontend checks**

```powershell
pnpm test -- AgentSection.test.tsx
pnpm typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/lib/api.ts frontend/app/components/AgentSection.tsx frontend/app/components/AgentSection.test.tsx frontend/app/SettingsModal.tsx
git commit -m "feat(frontend): add local-agent pairing and health"
```

---

### Task 8: Integração ponta a ponta local e documentação operacional

**Files:**

- Create: `backend/tests/test_agent_e2e.py`
- Modify: `docs/operacao/go-live.md`
- Modify: `RODAR-LOCAL.md`

**Interfaces:**

- Verifica o ciclo: user pairing → agent pair → enqueue → claim → heartbeat → complete → audit.

- [ ] **Step 1: Add an end-to-end API test**

O teste deve usar `client` autenticado para criar código, consumir o código sem JWT, criar um comando via `enqueue_command`, reivindicá-lo com `Authorization: Agent`, concluir e confirmar:

```python
assert command_json["status"] == "running"
assert completed_json["status"] == "completed"
assert "token_hash" not in str(completed_json)
assert db_session.query(models.AuditLog).filter_by(acao="agent_command_completed").count() == 1
```

- [ ] **Step 2: Run the end-to-end test**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_agent_e2e.py -v`

Expected: PASS after Tasks 1–7; any failure blocks the Marco A.

- [ ] **Step 3: Update runbooks with exact commands**

Add to both docs:

```powershell
cd backend
$PAIRING_CODE = "copie-o-codigo-exibido-no-Causor"
.\.venv\Scripts\python.exe -m app.local_agent pair `
  --api http://127.0.0.1:8000 `
  --code $PAIRING_CODE `
  --name "Notebook jurídico"

.\.venv\Scripts\python.exe -m app.local_agent run
```

State explicitly: hosted backend never opens a court browser; the agent must be online for authenticated read/filing commands.

- [ ] **Step 4: Run the complete foundation verification**

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_connector_contracts.py tests/test_agent_models.py tests/test_object_store.py tests/test_agent_auth.py tests/test_agent_commands.py tests/test_agent_api.py tests/test_local_agent.py tests/test_agent_e2e.py -q
.\.venv\Scripts\python.exe -m ruff check app tests
cd ..\frontend
pnpm test
pnpm typecheck
pnpm build
```

Expected: all commands exit `0`.

- [ ] **Step 5: Commit**

```powershell
git add backend/tests/test_agent_e2e.py docs/operacao/go-live.md RODAR-LOCAL.md
git commit -m "docs(agent): validate and document the local-agent workflow"
```

## Plan 1 acceptance gate

- [ ] `ProcessoInstancia` supports both degrees without changing `Processo` uniqueness.
- [ ] Agent token is hash-only in DB and never returned after pairing.
- [ ] Revoked agent receives 401.
- [ ] A command cannot be claimed or completed by another installation.
- [ ] Browser profile persists locally and is ignored by Git.
- [ ] Hosted API never launches headed Playwright.
- [ ] S3 credentials remain backend-only; the agent receives only a presigned URL.
- [ ] Foundation verification is green before starting Plans 2/3.
