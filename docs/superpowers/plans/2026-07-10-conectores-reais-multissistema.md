# Conectores reais PJe, eproc, e-SAJ e Projudi — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar e homologar leitura integral e protocolo assistido reais nas quatro famílias de sistemas com **um único acesso por tribunal** — o advogado loga uma vez, no computador dele, e a mesma sessão serve para baixar a íntegra dos autos (contexto da minuta) e para protocolar. Cobertura publicável baseada em testes live.

**Architecture:** O acesso ao tribunal deixa de ser dois conceitos (agente local + vault de cookie no backend) e passa a ser **um só**: um perfil de navegador persistente no agente da máquina do advogado, indexado por `(sistema, tribunal, grau)`. Esse perfil serve leitura (`read_process`) e protocolo (`prepare_filing`). O login também roda no agente, disparado pela UI: um comando enfileirado `open_court_login` abre a janela headed do portal na tela do advogado, ele loga uma vez e o agente reporta apenas `session_ready` — nenhum cookie, token ou certificado chega ao backend. O backend mantém um **estado de sessão derivado** por `(sistema, tribunal, grau)` (`desconectado | conectando | conectado | expirado`), alimentado pela conclusão do login e por health-checks read-only. Ao gerar minuta sem contexto completo, a UI abre um **assistente JIT** que encadeia pareamento → login → captura → geração automática, e reusa a mesma sessão no protocolo.

Drivers rodam exclusivamente no agente e implementam contratos separados de leitura e protocolo. Fluxos de navegação ficam em page objects por família; variações de URL/marker ficam em `ConnectorProfile` versionado. Testes unitários usam simuladores sanitizados; testes live read-only criam `ConnectorValidation` e são o único caminho para promover um perfil a `supported`.

**Tech Stack:** Python/Playwright, agentes/comandos do Plano 1, autos/manifests do Plano 2, YAML profiles, pytest opt-in live, FastAPI, PostgreSQL, Next.js.

## Global Constraints

- Depende do Plano 1; capacidades de leitura dependem também das Tasks 1–5 do Plano 2.
- **Um acesso serve tudo (caminho padrão, já implementado nas Tasks 1–5):** a mesma sessão autenticada de `(sistema, tribunal, grau)` no agente atende leitura e protocolo. Isso continua sendo o default, mas não é mais regra obrigatória — delegar a leitura (e, se necessário, a assinatura) a um vendor terceiro de confiança (Escavador, Judit, provedor de assinatura em nuvem) é uma alternativa válida quando acelerar chegar a um fluxo funcionando, especialmente para tribunais/sistemas onde o conector Playwright próprio ainda não existe ou está degradado.
- **Segredo bruto nunca entra em log ou prompt do backend**, independente de onde a sessão/certificado more (agente local ou vendor delegado): cookie, `storage_state`, perfil Playwright, certificado, senha, PIN ou OTP nunca são gravados em log/prompt. O backend guarda estado derivado (`conectado`/`expirado`), metadados, evidência e — quando aplicável — a referência da delegação ao vendor.
- O agente usa browser headed e perfil persistente; o backend hospedado nunca abre Playwright.
- O login é um comando enfileirado (`open_court_login`) executado pelo agente e disparável pela UI; a CLI `login` continua existindo como caminho manual de fallback.
- Um perfil é identificado por `(sistema, tribunal, grau, version_marker)`.
- Perfil novo inicia `experimental`; `supported` exige teste live recente e critérios completos.
- Uma conta por família valida apenas aquele perfil/tribunal/grau, não a família nacional inteira.
- Toda exploração live começa read-only; não clicar em assinar/protocolar durante descoberta.
- Fixture versionada é sintética ou sanitizada; não contém número real, partes, teor, cookies, tokens ou URLs com IDs privados.
- CAPTCHA, acesso negado, sessão expirada e layout desconhecido são estados explícitos e bloqueantes.
- Um ID de documento deve vir do portal/href estável; texto/título isolado não é identidade suficiente.
- Paginação só termina com evidência determinística; “não encontrei botão próximo” sem marker final é `cursor_incomplete`.
- `submit=True` só é permitido quando `profile.can_submit=True`, Gate OAB aprovado e ambiente/caso autorizados.
- Protocolo sem número e comprovante verificados nunca marca `Peticao.status="protocolada"`.
- `page.wait_for_text` é proibido; usar `Locator.wait_for`, `expect_download`, `expect_response` ou `wait_for_url` existentes no Playwright.
- O sistema do processo/instância é autoritativo; tribunal não pode fixar e-SAJ quando o caso já migrou para eproc.

---

## File map

**Create**

- `backend/alembic/versions/c9f7a1b5d4e3_connector_validation.py`
- `backend/alembic/versions/d1a8b2c6e5f4_court_session_state.py`
- `backend/app/connectors/profiles.py`
- `backend/app/connectors/registry.py`
- `backend/app/connectors/errors.py`
- `backend/app/connectors/sessions.py` — estado de sessão derivado + comando de login.
- `backend/app/connectors/live_validation.py`
- `backend/app/connectors/health.py`
- `backend/app/connectors/pje/reader.py`
- `backend/app/connectors/pje/filing.py`
- `backend/app/connectors/eproc/__init__.py`
- `backend/app/connectors/eproc/reader.py`
- `backend/app/connectors/eproc/filing.py`
- `backend/app/connectors/eproc/pages.py`
- `backend/app/connectors/esaj/__init__.py`
- `backend/app/connectors/esaj/reader.py`
- `backend/app/connectors/esaj/filing.py`
- `backend/app/connectors/esaj/pages.py`
- `backend/app/connectors/projudi/__init__.py`
- `backend/app/connectors/projudi/reader.py`
- `backend/app/connectors/projudi/filing.py`
- `backend/app/connectors/projudi/pages.py`
- `backend/app/connectors/simulators/base.py`
- `backend/app/connectors/simulators/pje.py`
- `backend/app/connectors/simulators/eproc.py`
- `backend/app/connectors/simulators/esaj.py`
- `backend/app/connectors/simulators/projudi.py`
- `backend/app/api/connector_routes.py`
- `backend/tests/test_connector_profiles.py`
- `backend/tests/test_connector_registry.py`
- `backend/tests/test_court_session_state.py`
- `backend/tests/test_court_login_command.py`
- `backend/tests/test_vault_session_removed.py`
- `backend/tests/test_pje_reader.py`
- `backend/tests/test_pje_filing_real.py`
- `backend/tests/test_eproc_connector.py`
- `backend/tests/test_esaj_connector.py`
- `backend/tests/test_projudi_connector.py`
- `backend/tests/test_connector_coverage.py`
- `backend/tests/test_minuta_assistant_flow.py`
- `backend/tests/live/test_court_reader_live.py`
- `backend/tests/live/test_court_filing_live.py`
- `docs/cobertura/tribunais.yaml`
- `docs/operacao/homologacao-conectores.md`
- `frontend/app/components/AcessoTribunalWizard.tsx`
- `frontend/app/components/AcessoTribunalWizard.test.tsx`
- `frontend/app/views/ConnectorCoverageView.tsx`
- `frontend/app/views/ConnectorCoverageView.test.tsx`

**Modify**

- `backend/app/sor/models.py` — `ConnectorValidation`, `CourtSessionState`; remover uso de `CredencialAssinatura(tipo="session")`.
- `backend/app/vault/service.py` — remover `store_court_session`, `find_active_session`, `load_court_session_payload`, `store_pje_session_reference`, `load_pje_session_payload`; manter `cloud_cert`.
- `backend/app/api/main.py` — remover `capturar_sessao_tribunal` e `cadastrar_sessao_pje`; incluir connector router; expor login/estado de sessão; `submit=False` seguro.
- `backend/app/capture/court_routing.py` — rota por instância, coexistência/migração e confirmação.
- `backend/app/capture/poll.py` — parar de depender de sessão do cofre.
- `backend/app/connectors/drivers.py` — usar registry genérico.
- `backend/app/connectors/pje/connector.py` — adapter temporário ou remoção após migração.
- `backend/app/connectors/pje/pages/login.py` — reaproveitar no comando `open_court_login`.
- `backend/app/connectors/pje/pages/peticionar.py` — retirar caminho quebrado.
- `backend/app/filing/package.py` — `FilingPackage` neutro com `ProcessoInstancia`, sem `storage_state`.
- `backend/app/queue/jobs.py` — enviar comando ao agente; parar de carregar sessão do cofre.
- `backend/app/local_agent/worker.py` — registrar handlers `open_court_login`, `read_process`, `prepare_filing`, `health_check`.
- `backend/app/local_agent/__main__.py` — manter `login` manual; handlers no `run`.
- `backend/app/settings.py` — live flags, validade da cobertura e freshness de sessão.
- `backend/app/cli.py` — comandos de validação/cobertura/health.
- `frontend/lib/api.ts` — login/estado de sessão, cobertura, assistente.
- `frontend/app/SettingsModal.tsx` — uma seção única “Acesso aos tribunais”.
- `frontend/app/components/AgentSection.tsx` — renomear/absorver em “Acesso aos tribunais”.
- `frontend/app/components/VaultSection.tsx` — remover captura de sessão; manter só assinatura em nuvem.
- `frontend/app/components/ProcessContextStatus.tsx` — abrir o assistente JIT ao gerar minuta.
- `frontend/app/views/ProtocolosView.tsx` — estados reais por driver.
- `frontend/app/views/OnboardingView.tsx` — texto do acesso unificado.
- `frontend/app/views/ConectoresView.tsx` — apontar para “Acesso aos tribunais”.
- `docs/estado.md`
- `docs/areas/pje-assistido.md`

---

### Task 1: Perfis versionados, registry e erros canônicos

**Files:**

- Create: `backend/app/connectors/errors.py`
- Create: `backend/app/connectors/profiles.py`
- Create: `backend/app/connectors/registry.py`
- Create: `backend/tests/test_connector_profiles.py`
- Create: `backend/tests/test_connector_registry.py`

**Interfaces:**

- Produces: `ConnectorProfile`, `ConnectorCapabilities`, `ConnectorRegistry`, `get_connector_registry()`.
- Errors: `SessionExpired`, `CaptchaRequired`, `AccessDenied`, `LayoutUnknown`, `CursorIncomplete`, `DocumentDownloadFailed`, `SignatureRequired`, `ReceiptNotVerified`, `SystemMigrated`.

- [ ] **Step 1: Write failing registry tests**

```python
# backend/tests/test_connector_registry.py
import pytest

from app.connectors.registry import ConnectorRegistry, UnsupportedConnectorProfile


class FakeReader:
    sistema = "PJe"


def test_registry_resolves_exact_profile_before_family_default():
    registry = ConnectorRegistry()
    registry.register_reader("PJe", FakeReader, tribunal="TJMG", grau="1")
    resolved = registry.reader("PJe", tribunal="TJMG", grau="1")
    assert resolved is FakeReader


def test_registry_fails_closed_without_registered_profile():
    registry = ConnectorRegistry()
    with pytest.raises(UnsupportedConnectorProfile):
        registry.reader("EPROC", tribunal="TJRS", grau="1")
```

- [ ] **Step 2: Run and verify missing registry**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_connector_profiles.py tests/test_connector_registry.py -v`

Expected: FAIL on import.

- [ ] **Step 3: Implement immutable profiles and exact-match registry**

```python
# backend/app/connectors/profiles.py
from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectorCapabilities:
    read_autos: bool
    read_secret: bool
    prepare_filing: bool
    submit_filing: bool
    download_receipt: bool


@dataclass(frozen=True)
class ConnectorProfile:
    key: str
    sistema: str
    tribunal: str
    grau: str
    url_base: str
    filing_url: str | None
    version_marker: str
    status: str
    capabilities: ConnectorCapabilities
    receipt_protocol_pattern: str | None = None

    def __post_init__(self):
        if self.grau not in {"1", "2"}:
            raise ValueError("grau must be 1 or 2")
        if self.status not in {"experimental", "supported", "degraded", "blocked"}:
            raise ValueError("invalid connector profile status")
```

`ConnectorRegistry` keys registration by `(sistema.casefold(), tribunal.upper(), grau)`. There is no silent family fallback in real mode. Sandbox remains separate. Registration of a duplicate key raises `DuplicateConnectorProfile`.

Canonical errors carry `code`, `retryable`, `requires_human` and `safe_detail`; their `str()` never includes URL query strings or page contents.

- [ ] **Step 4: Run registry tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_connector_profiles.py tests/test_connector_registry.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/connectors/errors.py backend/app/connectors/profiles.py backend/app/connectors/registry.py backend/tests/test_connector_profiles.py backend/tests/test_connector_registry.py
git commit -m "feat(connectors): add versioned profiles and fail-closed registry"
```

---

### Task 2: Login do tribunal como comando enfileirado e estado de sessão derivado

Unifica os dois acessos: o login passa a ser um comando que a UI dispara e o agente executa na máquina do advogado; o backend guarda apenas o estado derivado da sessão, nunca o cookie.

**Files:**

- Modify: `backend/app/sor/models.py`
- Create: `backend/alembic/versions/d1a8b2c6e5f4_court_session_state.py`
- Create: `backend/app/connectors/sessions.py`
- Modify: `backend/app/local_agent/worker.py`
- Modify: `backend/app/api/main.py`
- Create: `backend/tests/test_court_session_state.py`
- Create: `backend/tests/test_court_login_command.py`

**Interfaces:**

- Produces model `CourtSessionState(escritorio_id, installation_id, sistema, tribunal, grau, status, version_marker, last_confirmed_at, last_error_code)`; `status ∈ {desconectado, conectando, conectado, expirado}`.
- Produces: `request_court_login`, `apply_login_result`, `session_state_for`, `mark_session_expired`.
- Agent handler `open_court_login(payload)`; payload traz `sistema, tribunal, grau, url_login, processo_instancia_id`; resultado traz `session_ready: bool`, `version_marker`, `evidence`, **nunca** `storage_state`/cookie.
- User API: `POST /processos/{id}/tribunal/login` (enfileira `open_court_login` para a instância roteada); `GET /processos/{id}/tribunal/sessao` (estado derivado por instância).

- [ ] **Step 1: Write failing state + command tests**

```python
# backend/tests/test_court_session_state.py
from app.connectors.sessions import (
    apply_login_result,
    request_court_login,
    session_state_for,
)
from app.sor import models


def test_login_request_creates_connecting_state_and_command(db_session, seeded, agent_installation):
    state, command = request_court_login(
        db_session,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_login="https://pje.tjmg.jus.br/pje/login.seam",
        processo_instancia_id=1,
    )
    assert state.status == "conectando"
    assert command.tipo == "open_court_login"
    assert "storage_state" not in command.payload
    assert command.payload["url_login"].endswith("login.seam")


def test_successful_login_marks_connected_without_storing_cookie(db_session, seeded, agent_installation):
    state, command = request_court_login(
        db_session, escritorio_id=seeded.escritorio_id, sistema="PJe",
        tribunal="TJMG", grau="1", url_login="https://x/login.seam", processo_instancia_id=1,
    )
    apply_login_result(
        db_session,
        command=command,
        installation=agent_installation,
        resultado={"session_ready": True, "version_marker": "pje-2.5", "evidence": {"marker": "painel"}},
    )
    refreshed = session_state_for(
        db_session, escritorio_id=seeded.escritorio_id, sistema="PJe", tribunal="TJMG", grau="1"
    )
    assert refreshed.status == "conectado"
    assert refreshed.last_confirmed_at is not None
    # o estado nunca guarda cookie/sessão
    assert not hasattr(refreshed, "storage_state")
```

- [ ] **Step 2: Run and verify missing session module**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_court_session_state.py tests/test_court_login_command.py -v`

Expected: FAIL on import.

- [ ] **Step 3: Implement session state, login command and agent handler**

`CourtSessionState` model (unique por `escritorio_id, sistema, tribunal, grau`):

```python
class CourtSessionState(TimestampMixin, Base):
    __tablename__ = "court_session_state"
    __table_args__ = (
        UniqueConstraint("escritorio_id", "sistema", "tribunal", "grau", name="uq_court_session_route"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorio.id"), nullable=False, index=True)
    installation_id: Mapped[int | None] = mapped_column(ForeignKey("agent_installation.id"))
    sistema: Mapped[str] = mapped_column(String(20), nullable=False)
    tribunal: Mapped[str] = mapped_column(String(50), nullable=False)
    grau: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="desconectado")
    version_marker: Mapped[str | None] = mapped_column(String(80))
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
```

`request_court_login` faz upsert do estado para `conectando` e enfileira `open_court_login` via `enqueue_command` (Plano 1) com `idempotency_key="court-login:{sistema}:{tribunal}:{grau}:{YYYY-MM-DDTHH}"`. Payload contém somente `sistema, tribunal, grau, url_login, processo_instancia_id`.

`apply_login_result` transita `conectando → conectado` quando `session_ready is True`, grava `version_marker`, `last_confirmed_at`, `installation_id`; `session_ready is False` ou erro canônico marca `expirado`/`desconectado` com `last_error_code`. **Nunca** persiste cookie.

Handler do agente `open_court_login`: reusa `persistent_court_context` (Plano 1) para abrir a `url_login` headed; aguarda o marcador autenticado via `Locator.wait_for` (não `wait_for_text`); em sucesso retorna `{"session_ready": True, "version_marker": ..., "evidence": {...}}`; CAPTCHA/negado retornam erro canônico. A sessão fica só no perfil local. Registre o handler em `AgentWorker` no `run`.

`complete_command` (Plano 1) chama `apply_login_result` para comandos `open_court_login`. Rotas de usuário resolvem a instância pelo processo e delegam a `request_court_login`/`session_state_for`.

- [ ] **Step 4: Run session/command tests + migration**

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m pytest tests/test_court_session_state.py tests/test_court_login_command.py -q
```

Expected: PASS; `court_session_state` criada; nenhum teste observa cookie no backend.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/sor/models.py backend/alembic/versions/d1a8b2c6e5f4_court_session_state.py backend/app/connectors/sessions.py backend/app/local_agent/worker.py backend/app/api/main.py backend/tests/test_court_session_state.py backend/tests/test_court_login_command.py
git commit -m "feat(connectors): court login as queued agent command with derived session state"
```

---

### Task 3: Remover a captura de sessão no backend (vault de cookie)

Apaga o caminho legado que guardava o cookie do tribunal no backend. O acesso passa a ser exclusivamente o da Task 2.

**Files:**

- Modify: `backend/app/vault/service.py`
- Modify: `backend/app/api/main.py`
- Modify: `backend/app/queue/jobs.py`
- Modify: `backend/app/capture/poll.py`
- Create: `backend/alembic/versions/e2b9c3d7f6a5_deactivate_court_sessions.py` (migração de dados)
- Create: `backend/tests/test_vault_session_removed.py`
- Modify: `backend/tests/test_pje_vault_job.py`

**Interfaces:**

- Remove: `store_court_session`, `find_active_session`, `load_court_session_payload`, `store_pje_session_reference`, `load_pje_session_payload`.
- Remove endpoints: `POST /usuarios/{id}/sessoes-tribunal/capturar`, `POST /usuarios/{id}/pje-sessoes`.
- Keep: `store_signature_reference`, `list_signature_credentials`, `deactivate_signature_credential`, `_load_secret_from_reference` para `cloud_cert`.

- [ ] **Step 1: Write a regression proving the session vault is gone**

```python
# backend/tests/test_vault_session_removed.py
import pytest

from app.vault import service


def test_court_session_helpers_are_removed():
    for name in (
        "store_court_session",
        "find_active_session",
        "load_court_session_payload",
        "store_pje_session_reference",
    ):
        assert not hasattr(service, name), f"{name} deveria ter sido removido"


def test_session_capture_endpoints_return_404(client):
    assert client.post("/usuarios/1/sessoes-tribunal/capturar", json={}).status_code in (404, 405)
    assert client.post("/usuarios/1/pje-sessoes", json={}).status_code in (404, 405)


def test_cloud_cert_credentials_still_work(db_session, seeded):
    cred = service.store_signature_reference(
        db_session, usuario_id=1, provedor="BirdID", external_ref="ref-123"
    )
    assert cred.tipo == "cloud_cert"
```

- [ ] **Step 2: Run and observe current pass on the removed symbols**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_vault_session_removed.py -v`

Expected: FAIL because the symbols/endpoints still exist.

- [ ] **Step 3: Delete the session vault and migrate data**

- Remove as funções de sessão de `vault/service.py` e os imports órfãos; mantenha `cloud_cert`.
- Remove `capturar_sessao_tribunal` e `cadastrar_sessao_pje` de `api/main.py`, além dos schemas `CapturarSessaoRequest`/`CreatePjeSessionRequest` se não usados em outro lugar.
- Em `queue/jobs.py`, `run_pje_protocol_job` deixa de chamar `load_court_session_payload`/`find_active_session`; a sessão vem do agente (Task 5), não do cofre. `package` não carrega mais `storage_state`.
- Em `capture/poll.py`, remova a dependência da sessão do cofre.
- Migração de dados (`e2b9c3d7f6a5`, `down_revision="d1a8b2c6e5f4"`): `update credencial_assinatura set ativo = false where tipo = 'session'` e apagar segredos localdev correspondentes; segredos em `vault.decrypted_secrets` do provedor supabase para sessões são revogados no runbook. `cloud_cert` intacto.

- [ ] **Step 4: Run vault + job regressions**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_vault_session_removed.py tests/test_pje_vault_job.py tests/test_protocolo_roteado.py -q
```

Expected: PASS; nenhuma rota/serviço grava sessão de tribunal.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/vault/service.py backend/app/api/main.py backend/app/queue/jobs.py backend/app/capture/poll.py backend/alembic/versions backend/tests/test_vault_session_removed.py backend/tests/test_pje_vault_job.py
git commit -m "refactor(vault): remove backend court-session capture in favor of local agent"
```

---

### Task 4: Harness de simulador sanitizado e validação live

**Files:**

- Create: `backend/app/connectors/simulators/base.py`
- Create: `backend/app/connectors/simulators/pje.py`
- Create: `backend/app/connectors/simulators/eproc.py`
- Create: `backend/app/connectors/simulators/esaj.py`
- Create: `backend/app/connectors/simulators/projudi.py`
- Create: `backend/app/connectors/live_validation.py`
- Create: `backend/tests/live/test_court_reader_live.py`
- Create: `backend/tests/live/test_court_filing_live.py`
- Modify: `backend/app/cli.py`
- Create: `docs/operacao/homologacao-conectores.md`

**Interfaces:**

- CLI read-only reads `CAUSOR_LIVE_SYSTEM`, `CAUSOR_LIVE_COURT`, `CAUSOR_LIVE_DEGREE` and `CAUSOR_LIVE_PROCESS` from the local-agent environment.
- CLI filing prepare additionally reads `CAUSOR_LIVE_PETITION_PDF` and always forces `submit=false` unless a separate authorized submission command is used.
- Live tests require `RUN_COURT_LIVE=1` and local-agent profile; CI always skips.

- [ ] **Step 1: Write skip-safe live tests**

```python
import os
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_COURT_LIVE") != "1",
    reason="set RUN_COURT_LIVE=1 on the authorized lawyer machine",
)


def test_live_reader_returns_stable_complete_manifest(live_reader, live_target):
    first = live_reader.enumerate_documents(live_target)
    second = live_reader.enumerate_documents(live_target)
    assert first.cursor_complete is True
    assert first.source_fingerprint == second.source_fingerprint
    assert first.documentos
```

- [ ] **Step 2: Run default suite and verify live skip**

Run: `.\.venv\Scripts\python.exe -m pytest tests/live -v`

Expected: all live tests SKIPPED, exit `0`.

- [ ] **Step 3: Implement simulators and live record format**

Each simulator serves synthetic pages for: login marker, process search, autos with two pages, nested attachment, one secret label, filing form, signature gate and receipt. IDs are fixed `SIM-DOC-001..003`; PDF bytes contain no real data. O simulador de login expõe o marcador autenticado que o handler `open_court_login` (Task 2) usa.

`LiveValidationResult`:

```python
@dataclass(frozen=True)
class LiveValidationResult:
    profile_key: str
    capability: str
    passed: bool
    manifest_fingerprint: str | None
    documents_count: int | None
    error_code: str | None
    evidence_keys: tuple[str, ...]
    tested_at: datetime
```

CLI output redacts process number to its last four digits and writes the full result through the authenticated API; it never writes trace/DOM to the repository. Traces go to `%LOCALAPPDATA%\Causor\traces\{profile_key}\{timestamp}.zip`.

The runbook requires the YAML account record from the roadmap, legal approval and `permite_protocolo=false` during discovery.

- [ ] **Step 4: Run simulator and live-harness unit tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pje_simulator_integration.py tests/live -q
```

Expected: simulator PASS, live SKIPPED.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/connectors/simulators backend/app/connectors/live_validation.py backend/tests/live backend/app/cli.py docs/operacao/homologacao-conectores.md
git commit -m "test(connectors): add sanitized simulators and live validation harness"
```

---

### Task 5: Migrar execução real para o agente local

Leitura e protocolo passam a rodar no agente, usando a sessão já autenticada da Task 2; o backend nunca abre navegador.

**Files:**

- Modify: `backend/app/filing/package.py`
- Modify: `backend/app/connectors/drivers.py`
- Modify: `backend/app/queue/jobs.py`
- Modify: `backend/app/api/main.py`
- Modify: `backend/app/local_agent/worker.py`
- Create: `backend/tests/test_local_agent_dispatch.py`
- Modify: `backend/tests/test_pje_vault_job.py`

**Interfaces:**

- Server no longer calls `PjeBrowserSession` in real mode.
- `run_pje_protocol_job` enqueues `prepare_filing` and returns a queued/running job until agent result.
- Agent handlers: `open_court_login` (Task 2), `read_process`, `prepare_filing`, `health_check`.

- [ ] **Step 1: Write a regression proving hosted backend never launches Playwright**

```python
def test_real_filing_enqueues_local_agent_without_opening_browser(
    db_session, approved_petition_with_ready_context, monkeypatch
):
    monkeypatch.setattr(
        "app.connectors.pje.session.PjeBrowserSession.__enter__",
        lambda self: (_ for _ in ()).throw(AssertionError("server opened browser")),
    )
    job = run_pje_protocol_job(
        db_session,
        approved_petition_with_ready_context.id,
        usuario_id=approved_petition_with_ready_context.aprovada_por,
        filing_mode="real",
        submit=False,
    )
    command = db_session.query(models.AgentCommand).filter_by(tipo="prepare_filing").one()
    assert job.status in {"queued", "running"}
    assert command.payload["peticao_id"] == approved_petition_with_ready_context.id
    assert "storage_state" not in command.payload
```

- [ ] **Step 2: Run and observe current browser-path failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_local_agent_dispatch.py -v`

Expected: FAIL because real mode still instantiates `PjeDriver` in the backend.

- [ ] **Step 3: Implement server/agent split**

`build_filing_package` uses `ProcessoInstancia`, produces generic `FilingPackage` (sem `storage_state`, sem `pje_base_url`) e escreve o PDF renderizado no storage privado. O comando `prepare_filing` carrega `peticao_id`, `processo_instancia_id`, `sistema`, `tribunal`, `grau`, `pdf_object_key`, `submit=False`; o agente usa o perfil de sessão local e obtém o PDF por URL assinada curta.

Antes de enfileirar `prepare_filing`, o job checa `session_state_for(...).status == "conectado"`; se `expirado/desconectado`, retorna estado acionável (`session_expired`) que a UI transforma em passo de login do assistente — não abre navegador no servidor.

On agent completion:

- `ready_to_sign` completes job but leaves petition `aprovada`;
- `protocolado` requires verified `protocolo` and `receipt_object_key` before changing status;
- any canonical connector error marks job failed/retryable and returns petition to `aprovada`; `session_expired` também marca `CourtSessionState` como `expirado`.

Remove the frontend/API path that sends `submit=True` by default. `submit` is server-decided from supported profile + explicit Gate OAB action.

- [ ] **Step 4: Run dispatch/job tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_local_agent_dispatch.py tests/test_pje_vault_job.py tests/test_protocolo_roteado.py -q
```

Expected: PASS; no server browser creation; nenhum `storage_state` em payload.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/filing/package.py backend/app/connectors/drivers.py backend/app/queue/jobs.py backend/app/api/main.py backend/app/local_agent/worker.py backend/tests/test_local_agent_dispatch.py backend/tests/test_pje_vault_job.py
git commit -m "refactor(connectors): execute real court actions in local agent"
```

---

### Task 6: PJe real — leitura integral antes do protocolo

**External gate:** conta PJe autorizada com tribunal, grau, URL e processo read-only seguro.

**Files:**

- Create: `backend/app/connectors/pje/reader.py`
- Create: `backend/app/connectors/pje/filing.py`
- Modify: `backend/app/connectors/pje/pages/login.py`
- Modify: `backend/app/connectors/pje/pages/processo.py`
- Modify: `backend/app/connectors/pje/pages/peticionar.py`
- Create: `backend/tests/test_pje_reader.py`
- Create: `backend/tests/test_pje_filing_real.py`
- Modify: `backend/app/connectors/simulators/pje.py`

**Interfaces:**

- Produces: `PjeReaderDriver`, `PjeFilingDriver`.
- Register exact profile only after live read passes.

- [ ] **Step 1: Extend the synthetic PJe simulator and write reader tests**

The simulator must expose three document rows over two pages. Reader test asserts:

```python
snapshot = driver.enumerate_documents(target)
assert snapshot.cursor_complete is True
assert [item.external_id for item in snapshot.documentos] == [
    "SIM-DOC-001", "SIM-DOC-002", "SIM-DOC-003"
]
assert driver.download_document(target, snapshot.documentos[0]).startswith(b"%PDF-")
```

Add tests for secret label, attachment parent ID, expired session, CAPTCHA and missing next-page terminator. A sessão vem do perfil autenticado pelo `open_court_login`; sessão expirada levanta `SessionExpired` (não tenta relogar sozinho).

- [ ] **Step 2: Run and verify missing reader**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pje_reader.py -v`

Expected: FAIL because `PjeReaderDriver` does not exist.

- [ ] **Step 3: Implement PJe page-object workflow and fix filing**

Reader workflow:

```text
ensure authenticated marker (perfil da sessão local; senão SessionExpired)
→ Processo > Pesquisar > Processo
→ normalize CNJ number and open exact result
→ open Autos/Detalhes
→ enumerate visible document rows and stable href/data-id
→ follow deterministic next-page marker until disabled/final count
→ download via expect_download or authenticated context.request
→ re-enumerate after all downloads
```

Filing fixes:

- replace `page.wait_for_text(...)` with a receipt locator and `locator.wait_for(state="visible", timeout=...)`;
- `submit=False` stops before the first irreversible click;
- `submit=True` checks `profile.capabilities.submit_filing`, records screenshot immediately before click and waits for both protocol number and receipt link;
- call `baixar_comprovante_pdf`, validate PDF and upload receipt;
- protocol regex must be profile-scoped and the matched label must contain `protocolo`.

Any raw Playwright error is mapped to a canonical connector error; it must not leave command/job `running`.

- [ ] **Step 4: Run simulator tests, then live read-only validation**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pje_reader.py tests/test_pje_filing_real.py tests/test_pje_simulator_integration.py -q
$env:RUN_COURT_LIVE='1'
$env:CAUSOR_LIVE_SYSTEM='PJe'
$env:CAUSOR_LIVE_COURT='TJMG'
$env:CAUSOR_LIVE_DEGREE='1'
$env:CAUSOR_LIVE_PROCESS='numero-autorizado-no-agente-local'
.\.venv\Scripts\python.exe -m pytest tests/live/test_court_reader_live.py -v -k live_reader
```

Expected: all simulator tests PASS; live read records fingerprint/count. Do not run live filing submit in this task.

- [ ] **Step 5: Commit only after live read passes**

```powershell
git add backend/app/connectors/pje backend/tests/test_pje_reader.py backend/tests/test_pje_filing_real.py backend/app/connectors/simulators/pje.py
git commit -m "feat(pje): read complete case files and harden filing gate"
```

---

### Task 7: eproc real — eventos, documentos e movimentação

**External gate:** conta eproc autorizada, preferencialmente uma instância com processo em 1º grau e vínculo ao 2º.

**Files:**

- Create: `backend/app/connectors/eproc/__init__.py`
- Create: `backend/app/connectors/eproc/pages.py`
- Create: `backend/app/connectors/eproc/reader.py`
- Create: `backend/app/connectors/eproc/filing.py`
- Create: `backend/tests/test_eproc_connector.py`
- Modify: `backend/app/connectors/simulators/eproc.py`

**Interfaces:**

- Produces: `EprocReaderDriver`, `EprocFilingDriver`.

- [ ] **Step 1: Write simulator tests for event-table documents**

```python
def test_eproc_reads_all_event_documents_and_attachments(eproc_driver, target):
    snapshot = eproc_driver.enumerate_documents(target)
    assert snapshot.cursor_complete
    assert [(d.external_id, d.parent_external_id) for d in snapshot.documentos] == [
        ("EVT-10-DOC-1", None),
        ("EVT-11-DOC-1", None),
        ("EVT-11-DOC-2", "EVT-11-DOC-1"),
    ]
```

Also test event pagination, “documento restrito”, process-not-found and redirection to 2º grau.

- [ ] **Step 2: Run and verify missing eproc driver**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_eproc_connector.py -v`

Expected: FAIL on import.

- [ ] **Step 3: Implement eproc-specific workflows**

Reader enumerates the event table in chronological portal order; stable ID combines portal event ID + document ID from link parameters, never the visible description. Filing opens `Movimentar/Peticionar`, selects the event/type, associates the deadline when present, uploads PDF and stops before `Peticionar/Finalizar` unless submit capability is live-approved.

The 2º-degree redirect creates/updates a separate `ProcessoInstancia`; it never mutates the 1º-degree instance. Cada instância tem seu próprio `CourtSessionState`; logar no 1º grau não presume sessão no 2º.

- [ ] **Step 4: Run simulator then live read-only**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_eproc_connector.py -q
$env:RUN_COURT_LIVE='1'
$env:CAUSOR_LIVE_SYSTEM='EPROC'
$env:CAUSOR_LIVE_COURT='TJRS'
$env:CAUSOR_LIVE_DEGREE='1'
$env:CAUSOR_LIVE_PROCESS='numero-autorizado-no-agente-local'
.\.venv\Scripts\python.exe -m pytest tests/live/test_court_reader_live.py -v -k live_reader
```

Expected: simulator PASS and stable live fingerprint across two enumerations.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/connectors/eproc backend/app/connectors/simulators/eproc.py backend/tests/test_eproc_connector.py
git commit -m "feat(eproc): add event-based reader and filing preparation"
```

---

### Task 8: e-SAJ real — autos, serviços por grau e comprovante

**External gate:** conta e-SAJ autorizada e processo que ainda tramite no e-SAJ.

**Files:**

- Create: `backend/app/connectors/esaj/__init__.py`
- Create: `backend/app/connectors/esaj/pages.py`
- Create: `backend/app/connectors/esaj/reader.py`
- Create: `backend/app/connectors/esaj/filing.py`
- Create: `backend/tests/test_esaj_connector.py`
- Modify: `backend/app/connectors/simulators/esaj.py`

**Interfaces:**

- Produces: `EsajReaderDriver`, `EsajFilingDriver`.

- [ ] **Step 1: Write tests for 1º/2º service separation and full document list**

```python
def test_esaj_profile_uses_degree_specific_service(esaj_profiles):
    assert "820100" in esaj_profiles["1"].filing_url
    assert "820200" in esaj_profiles["2"].filing_url


def test_esaj_reader_rejects_partial_document_popup(esaj_reader, target):
    with pytest.raises(CursorIncomplete):
        esaj_reader.enumerate_documents(target)
```

- [ ] **Step 2: Run and verify missing driver**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_esaj_connector.py -v`

Expected: FAIL on import.

- [ ] **Step 3: Implement e-SAJ workflows**

Reader enters the authenticated process view, enumerates all document rows across the full digital case view and downloads by the portal document identifier. Filing uses the profile's degree-specific intermediate-petition service, fills destination/process/category/type, uploads PDF and stops before final send. Receipt verification requires the protocol-data screen plus downloadable receipt or authenticated receipt URL.

If the portal says the forum/competence migrated to eproc, raise `SystemMigrated(target_system="EPROC")`; routing creates/selects an EPROC instance instead of retrying e-SAJ, e o assistente JIT (Task 11) pede o login no eproc.

- [ ] **Step 4: Run simulator then live read-only**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_esaj_connector.py -q
$env:RUN_COURT_LIVE='1'
$env:CAUSOR_LIVE_SYSTEM='e-SAJ'
$env:CAUSOR_LIVE_COURT='TJSP'
$env:CAUSOR_LIVE_DEGREE='1'
$env:CAUSOR_LIVE_PROCESS='numero-autorizado-no-agente-local'
.\.venv\Scripts\python.exe -m pytest tests/live/test_court_reader_live.py -v -k live_reader
```

Expected: PASS and validation stored for the exact e-SAJ profile.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/connectors/esaj backend/app/connectors/simulators/esaj.py backend/tests/test_esaj_connector.py
git commit -m "feat(esaj): add degree-aware reader and filing preparation"
```

---

### Task 9: Projudi real — autos legados e assinatura assistida

**External gate:** conta Projudi autorizada com tribunal explicitamente identificado; não assumir que TJPR atual usa Projudi para o processo escolhido.

**Files:**

- Create: `backend/app/connectors/projudi/__init__.py`
- Create: `backend/app/connectors/projudi/pages.py`
- Create: `backend/app/connectors/projudi/reader.py`
- Create: `backend/app/connectors/projudi/filing.py`
- Create: `backend/tests/test_projudi_connector.py`
- Modify: `backend/app/connectors/simulators/projudi.py`

**Interfaces:**

- Produces: `ProjudiReaderDriver`, `ProjudiFilingDriver`.

- [ ] **Step 1: Write tests for document table and signer handoff**

```python
def test_projudi_reader_uses_portal_document_ids(projudi_reader, target):
    snapshot = projudi_reader.enumerate_documents(target)
    assert [d.external_id for d in snapshot.documentos] == ["MOV-5-ARQ-1", "MOV-8-ARQ-1"]


def test_projudi_filing_stops_before_java_or_external_signer(projudi_filing, package):
    result = projudi_filing.prepare_filing(package, submit=False)
    assert result.checkpoint == "ready_to_sign"
    assert result.irreversible is False
```

- [ ] **Step 2: Run and verify missing driver**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_projudi_connector.py -v`

Expected: FAIL on import.

- [ ] **Step 3: Implement Projudi-specific workflows**

Reader opens the process movements/documents view, captures stable movement/file IDs, handles nested frames explicitly and proves the end of pagination. Filing selects petition type, uploads PDF and treats Java applet/external signer/PIN as human handoff; no automation bypasses signer prompts.

Unsupported legacy variant raises `LayoutUnknown` with version marker/evidence, never falls back to generic text clicking.

- [ ] **Step 4: Run simulator then live read-only**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_projudi_connector.py -q
$env:RUN_COURT_LIVE='1'
$env:CAUSOR_LIVE_SYSTEM='Projudi'
$env:CAUSOR_LIVE_COURT='TJGO'
$env:CAUSOR_LIVE_DEGREE='1'
$env:CAUSOR_LIVE_PROCESS='numero-autorizado-no-agente-local'
.\.venv\Scripts\python.exe -m pytest tests/live/test_court_reader_live.py -v -k live_reader
```

Expected: PASS and exact profile validation.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/connectors/projudi backend/app/connectors/simulators/projudi.py backend/tests/test_projudi_connector.py
git commit -m "feat(projudi): add legacy-case reader and assisted filing"
```

---

### Task 10: Validação persistida, matriz de cobertura e promoção segura

**Files:**

- Modify: `backend/app/sor/models.py`
- Create: `backend/alembic/versions/c9f7a1b5d4e3_connector_validation.py`
- Create: `backend/app/api/connector_routes.py`
- Create: `backend/app/connectors/health.py`
- Modify: `backend/app/api/main.py`
- Modify: `backend/app/connectors/live_validation.py`
- Modify: `backend/app/cli.py`
- Create: `backend/tests/test_connector_coverage.py`
- Create: `docs/cobertura/tribunais.yaml`

**Interfaces:**

- Produces: `ConnectorValidation`, `coverage_status`, `promote_profile`.
- API: `GET /connectors/coverage`, `GET /connectors/coverage/{profile_key}`.
- Health: `enqueue_connector_health_checks` creates read-only `health_check` agent commands; it verifies login marker, version marker and profile URL without opening or downloading a real process. Um `health_check` que falha o marcador de login marca também `CourtSessionState` como `expirado`.

- [ ] **Step 1: Write promotion tests**

```python
def test_profile_cannot_be_supported_without_recent_live_read(db_session, profile):
    status = coverage_status(db_session, profile=profile, max_age_days=30)
    assert status.state == "experimental"
    assert "live_read_missing" in status.reasons


def test_profile_degrades_when_recent_validation_fails(db_session, supported_profile):
    record_validation(db_session, profile=supported_profile, capability="read_autos", passed=False, error_code="layout_unknown")
    status = coverage_status(db_session, profile=supported_profile, max_age_days=30)
    assert status.state == "degraded"
```

- [ ] **Step 2: Run and verify missing validation model**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_connector_coverage.py -v`

Expected: FAIL.

- [ ] **Step 3: Implement persisted validation and promotion rules**

Model:

```python
class ConnectorValidation(TimestampMixin, Base):
    __tablename__ = "connector_validation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorio.id"), nullable=False, index=True)
    installation_id: Mapped[int] = mapped_column(ForeignKey("agent_installation.id"), nullable=False)
    profile_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    capability: Mapped[str] = mapped_column(String(50), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    documents_count: Mapped[int | None] = mapped_column(Integer)
    manifest_fingerprint: Mapped[str | None] = mapped_column(String(71))
    error_code: Mapped[str | None] = mapped_column(String(80))
    evidence: Mapped[dict | None] = mapped_column(JSON)
    agent_version: Mapped[str | None] = mapped_column(String(40))
    app_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    tested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

The migration uses `down_revision="e2b9c3d7f6a5"` (a migração de dados da Task 3), so connector validation is applied after the session-state schema and the vault cleanup.

Promotion requires, within 30 days and same app/profile revision:

- `read_autos` pass with at least one document;
- `prepare_filing` pass with `submit=False`;
- secret read pass only to advertise `read_secret`;
- `submit_filing` pass only in authorized homologation/safe case;
- no later failed validation.

`health.py` enqueues at most one health command per profile/24h using the command idempotency key `connector-health:{profile_key}:{YYYY-MM-DD}`. A failed version/login marker changes effective state to `degraded`; it does not edit the code profile automatically. Add settings `connector_validation_max_age_days=30` and `connector_health_interval_hours=24`, plus CLI `connector-health-due` for the production cron.

Generate `docs/cobertura/tribunais.yaml` from the registry. The file contains public-safe status only; validation evidence remains private DB data.

- [ ] **Step 4: Run coverage and schema tests**

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m pytest tests/test_connector_coverage.py -q
.\.venv\Scripts\python.exe -m app.cli export-connector-coverage --output ..\docs\cobertura\tribunais.yaml
```

Expected: PASS and deterministic YAML diff.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/sor/models.py backend/alembic/versions/c9f7a1b5d4e3_connector_validation.py backend/app/api/connector_routes.py backend/app/api/main.py backend/app/connectors/live_validation.py backend/app/connectors/health.py backend/app/cli.py backend/tests/test_connector_coverage.py docs/cobertura/tribunais.yaml
git commit -m "feat(connectors): persist live validation and coverage status"
```

---

### Task 11: Assistente JIT de minuta e tela única de acesso aos tribunais

Ao clicar em “Gerar minuta” sem o contexto pronto, um assistente único encadeia pareamento → login → captura → geração automática, reusando a mesma sessão no protocolo. As Configurações passam a ter uma seção só: “Acesso aos tribunais”.

**Files:**

- Modify: `frontend/lib/api.ts`
- Create: `frontend/app/components/AcessoTribunalWizard.tsx`
- Create: `frontend/app/components/AcessoTribunalWizard.test.tsx`
- Modify: `frontend/app/components/ProcessContextStatus.tsx`
- Create: `frontend/app/views/ConnectorCoverageView.tsx`
- Create: `frontend/app/views/ConnectorCoverageView.test.tsx`
- Modify: `frontend/app/SettingsModal.tsx`
- Modify: `frontend/app/components/AgentSection.tsx`
- Modify: `frontend/app/components/VaultSection.tsx`
- Modify: `frontend/app/views/ProtocolosView.tsx`
- Modify: `frontend/app/views/OnboardingView.tsx`
- Modify: `frontend/app/views/ConectoresView.tsx`
- Create: `backend/tests/test_minuta_assistant_flow.py`
- Modify: `docs/estado.md`
- Modify: `docs/areas/pje-assistido.md`

**Interfaces:**

- Wizard steps: `agent_offline`, `route_confirm`, `login`, `capturing`, `processing`, `ready`, `error`.
- Session/coverage states surfaced: `desconectado`, `conectando`, `conectado`, `expirado`; `experimental`, `supported`, `degraded`, `blocked`.
- Human actions: `Instalar/parear agente`, `Confirmar tribunal`, `Abrir portal para login`, `Retomar captura`, `Assumir protocolo`, `Ver evidência`.

- [ ] **Step 1: Write the assistant flow test (backend orchestration)**

```python
# backend/tests/test_minuta_assistant_flow.py
def test_generate_minuta_without_context_returns_actionable_next_step(
    client, processo_sem_contexto
):
    resp = client.post(f"/processos/{processo_sem_contexto.id}/minuta")
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "process_context_incomplete"
    # o passo acionável diz à UI o que abrir no assistente
    assert body["next_step"] in {"pair_agent", "court_login", "capture_autos"}
    assert body["rota"]["sistema"] and body["rota"]["grau"]


def test_after_login_and_capture_minuta_generates_without_new_click(
    client, processo_pronto_para_capturar, fake_agent
):
    # login → captura completa (Plano 2) → contexto ready
    fake_agent.complete_login(processo_pronto_para_capturar)
    fake_agent.complete_capture(processo_pronto_para_capturar)
    resp = client.post(f"/processos/{processo_pronto_para_capturar.id}/minuta")
    assert resp.status_code == 200
    assert resp.json()["peticao_id"]
```

- [ ] **Step 2: Run and verify the actionable-step contract is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_minuta_assistant_flow.py -v`

Expected: FAIL because the 409 payload does not yet carry `next_step`/`rota`.

- [ ] **Step 3: Implement the actionable gate + wizard + unified settings**

Backend: `require_ready_context` (Plano 2) passa a devolver, no 409, `next_step` (`pair_agent` se não há agente online; `court_login` se `CourtSessionState != conectado`; `capture_autos` se conectado mas sem captura completa) e `rota` (sistema/tribunal/grau resolvidos por `resolve_route` a partir do CNJ, autoritativo pela instância). Nenhuma ação irreversível é disparada pelo gate.

Frontend `AcessoTribunalWizard`:

- **agent_offline:** se não há agente pareado/online, mostra o comando de pareamento (reusa `AgentSection`) e aguarda ficar online (polling do estado atual).
- **route_confirm:** mostra a rota resolvida (`PJe · TJMG · 1º grau`); o advogado confirma ou corrige o sistema/grau (coexistência e-SAJ/eproc no TJSP). A confirmação alimenta a instância.
- **login:** botão “Abrir portal para login” chama `POST /processos/{id}/tribunal/login`; a janela headed abre na máquina do advogado; o wizard faz polling de `GET /processos/{id}/tribunal/sessao` até `conectado`.
- **capturing/processing:** reusa o status do Plano 2 (`statusAutos`) mostrando enumeração → downloads → OCR → resumos.
- **ready:** dispara a geração da minuta automaticamente (sem novo clique) e fecha o assistente.
- **error:** erros canônicos (`captcha_required`, `session_expired`, `layout_unknown`, `receipt_not_verified`) com ação de retomada humana.

`ProcessContextStatus` deixa de ter o botão “Gerar minuta” desabilitado + “Capturar autos” separados: passa a ter um único “Gerar minuta” que, quando bloqueado, abre o `AcessoTribunalWizard` no passo certo. O override excepcional (Plano 2) permanece disponível.

Configurações: `SettingsModal` passa a ter **uma** seção “Acesso aos tribunais” que combina o agente pareado e a lista de tribunais conectados (com estado de sessão por `(sistema, tribunal, grau)` e ação “Reconectar”). `VaultSection` perde a captura de sessão “Conectar tribunal” e fica só com as referências de assinatura em nuvem (`cloud_cert`). `OnboardingView` e `ConectoresView` passam a descrever o acesso único (sem menção a “CLI” ou “Vault” para sessão).

`ConnectorCoverageView`: tabela tribunal/sistema/grau/ler autos/sigiloso/preparar/protocolar/última validação live/estado; `degraded`/`blocked` mostram erro canônico e ação. `ProtocolosView` distingue `ready_to_sign`, `signature_required`, `protocolado`, `layout_unknown`, `session_expired`, `captcha_required`, `receipt_not_verified`.

- [ ] **Step 4: Run full product verification**

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
cd ..\frontend
pnpm test
pnpm typecheck
pnpm build
```

Expected: all exit `0`; live tests remain skipped unless explicitly enabled.

- [ ] **Step 5: Commit**

```powershell
git add frontend/lib/api.ts frontend/app/components/AcessoTribunalWizard.tsx frontend/app/components/AcessoTribunalWizard.test.tsx frontend/app/components/ProcessContextStatus.tsx frontend/app/views/ConnectorCoverageView.tsx frontend/app/views/ConnectorCoverageView.test.tsx frontend/app/SettingsModal.tsx frontend/app/components/AgentSection.tsx frontend/app/components/VaultSection.tsx frontend/app/views/ProtocolosView.tsx frontend/app/views/OnboardingView.tsx frontend/app/views/ConectoresView.tsx backend/tests/test_minuta_assistant_flow.py docs/estado.md docs/areas/pje-assistido.md
git commit -m "feat(frontend): JIT minuta assistant and unified court access"
```

---

### Task 12: Ondas nacionais por perfil de tribunal e grau

**Files:**

- Modify: `docs/cobertura/tribunais.yaml`
- Modify: `docs/operacao/homologacao-conectores.md`
- Create: `backend/tests/test_national_coverage_contract.py`

**Interfaces:**

- Produces a repeatable certification loop; no court is promoted by manual YAML edit alone.

- [ ] **Step 1: Add coverage contract test**

The test loads the YAML and asserts:

```python
assert row["state"] in {"experimental", "supported", "degraded", "blocked"}
if row["state"] == "supported":
    assert row["last_live_validation"]
    assert row["read_autos"] is True
    assert row["degree"] in {"1", "2"}
```

- [ ] **Step 2: Run the coverage contract**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_national_coverage_contract.py -v`

Expected: PASS for the generated matrix.

- [ ] **Step 3: Execute certification waves**

Wave order:

1. Advisor reference profiles: one PJe, one eproc, one e-SAJ, one Projudi.
2. Same four families in missing degree for those courts.
3. Remaining PJe courts grouped by proven version marker, never by URL pattern alone.
4. eproc courts/sections.
5. e-SAJ courts while migrations are tracked per process.
6. Projudi legacy courts.
7. Residual systems discovered by DataJud are `blocked` until a dedicated driver exists.

For every profile, run read twice, download every document, process one textual and one scanned PDF, test secret when authorized, prepare filing with `submit=False`, export coverage and review evidence.

- [ ] **Step 4: Verify each wave before promotion**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_national_coverage_contract.py tests/test_connector_coverage.py -q
.\.venv\Scripts\python.exe -m app.cli export-connector-coverage --output ..\docs\cobertura\tribunais.yaml
git diff --check
```

Expected: PASS; only profiles with matching live records become supported.

- [ ] **Step 5: Commit one wave at a time**

```powershell
git add docs/cobertura/tribunais.yaml docs/operacao/homologacao-conectores.md backend/tests/test_national_coverage_contract.py
git commit -m "chore(coverage): certify connector profile wave"
```

## Plan 3 acceptance gate

- [ ] Um único acesso por tribunal serve leitura e protocolo; não há segundo login nem cofre de sessão.
- [ ] Nenhum cookie/sessão de tribunal existe no backend; `CourtSessionState` guarda só estado derivado.
- [ ] O login roda no agente, disparado pela UI (`open_court_login`), e o backend real nunca abre navegador.
- [ ] Gerar minuta sem contexto abre o assistente no passo certo e, ao ficar pronto, gera a minuta sem novo clique.
- [ ] PJe, eproc, e-SAJ and Projudi each pass simulator reader/filing tests.
- [ ] Four advisor profiles pass live read twice with stable fingerprint.
- [ ] Each downloaded live manifest reaches `CapturaAutos.complete` through Plan 2.
- [ ] `submit=False` passes on all four reference profiles.
- [ ] No profile advertises submit without an authorized live submission/receipt test.
- [ ] Current TJSP cases route between e-SAJ/eproc by process instance.
- [ ] Unknown layouts fail closed with evidence.
- [ ] Coverage UI and YAML reflect live evidence, not code existence.
- [ ] Full backend/frontend verification is green before Marco C/D.
