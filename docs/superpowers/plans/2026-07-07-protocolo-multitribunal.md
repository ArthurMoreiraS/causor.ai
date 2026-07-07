# Protocolo multi-tribunal (cofre + roteamento + captura UI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o Causor rotear e protocolar cada minuta no sistema correto do tribunal (PJe/e-SAJ/EPROC/Projudi), com captura de sessão pela UI e um protocolo determinístico à prova de falhas para a demo.

**Architecture:** Registro de roteamento `tribunal+grau → sistema + URL` alimenta um cofre de credenciais multi-tribunal; um `FilingDriver` por sistema é despachado automaticamente a partir da minuta; a demo roda no `SandboxDriver` (determinístico, com número de protocolo + comprovante + screenshots), mantendo o conector PJe real atrás da mesma interface e o gate humano antes do ato irreversível.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, Playwright, pytest; Next.js 15 + React 19 (TypeScript), Vitest.

## Global Constraints

- **Segredos nunca em prompt/log.** O cofre guarda só `storage_state` (cookie) e referências não-secretas; nunca senha, certificado bruto, PIN ou OTP. (AGENTS.md #1)
- **Gate humano antes de todo ato irreversível** (protocolo). Mantido e visível. (AGENTS.md #2)
- **Auditoria imutável** de cada passo via `audit_log`. (AGENTS.md #3)
- **APIs oficiais antes de scraping**; Playwright é só para *ação*. (AGENTS.md #4)
- **TDD.** Todo comportamento novo entra por teste primeiro. Rodar do diretório `backend/`.
- **Modelos rótulo canônico do sistema:** exatamente `"PJe"`, `"e-SAJ"`, `"EPROC"`, `"Projudi"` (como em `court_systems.py`).
- **Comandos backend** (Windows): `./.venv/Scripts/python.exe -m pytest -q`, `./.venv/Scripts/python.exe -m ruff check .`.
- **Sandbox honestamente rotulado** como ambiente Causor de homologação; nunca se apresenta como protocolo real. Guard `CAUSOR_PJE_ALLOW_PROD` mantido.
- **Sem quebrar o verde atual:** `test_court_systems.py`, `test_pje_vault_job.py`, `test_pje_connector.py`, `test_signing_providers.py`, `test_api.py` devem continuar passando (usar wrappers/aliases quando renomear).

---

### Task 1: Registro de roteamento de tribunais (`court_routing`)

Estende a dedução de sistema para carregar as URLs reais de login e peticionamento por `(tribunal, grau)`.

**Files:**
- Create: `backend/app/capture/court_routing.py`
- Create: `backend/tests/test_court_routing.py`
- Modify: `backend/app/capture/court_systems.py` (derivar `sistema_para_tribunal` do registro)

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) CourtRoute(tribunal: str, grau: str, sistema: str, url_login: str | None, url_peticionamento: str | None, verificado: bool, observacao: str | None = None)`
  - `resolve_route(tribunal: str | None, grau: str = "1") -> CourtRoute | None`
  - `sistema_para_tribunal(tribunal: str | None) -> str | None` (mantida em `court_systems.py`, agora delegando ao registro)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_court_routing.py
from app.capture.court_routing import CourtRoute, resolve_route


def test_tjsp_routes_to_esaj_with_peticionamento_url():
    route = resolve_route("TJSP", "1")
    assert route is not None
    assert route.sistema == "e-SAJ"
    assert "esaj.tjsp.jus.br" in route.url_peticionamento
    assert route.verificado is True


def test_tjsp_second_degree_has_its_own_url():
    r1 = resolve_route("TJSP", "1")
    r2 = resolve_route("TJSP", "2")
    assert r1.url_peticionamento != r2.url_peticionamento


def test_unknown_tribunal_falls_back_to_pje_without_url():
    route = resolve_route("TJXX", "1")
    assert route.sistema == "PJe"
    assert route.url_peticionamento is None
    assert route.verificado is False


def test_none_tribunal_returns_none():
    assert resolve_route(None) is None


def test_case_and_whitespace_insensitive():
    assert resolve_route(" tjsp ", "1").sistema == "e-SAJ"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_court_routing.py -v`
Expected: FAIL with `ModuleNotFoundError: app.capture.court_routing`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/capture/court_routing.py
"""Registro tribunal+grau -> sistema + URLs de login/peticionamento.

Best-effort e sobreponível (sistemas migram; TJSP->eproc em curso). DataJud é
autoritativo quando traz o campo. Toda entrada verificada contra o site oficial
carrega verificado=True; as demais são palpite a confirmar (verificado=False).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CourtRoute:
    tribunal: str
    grau: str
    sistema: str
    url_login: str | None
    url_peticionamento: str | None
    verificado: bool
    observacao: str | None = None


# Fonte por sistema. url_peticionamento por grau: {"1": ..., "2": ...}.
_ESAJ = {
    "TJSP": {
        "login": "https://esaj.tjsp.jus.br/esaj/portal.do?servico=740000",
        "pet": {
            "1": "https://esaj.tjsp.jus.br/esaj?servico=820100",
            "2": "https://esaj.tjsp.jus.br/esaj?servico=820200",
        },
        "verificado": True,
    },
    # Confirmar URLs na implementação (verificado=False até conferir).
    "TJMS": {"login": None, "pet": {}, "verificado": False},
    "TJCE": {"login": None, "pet": {}, "verificado": False},
    "TJAL": {"login": None, "pet": {}, "verificado": False},
    "TJAC": {"login": None, "pet": {}, "verificado": False},
}
_EPROC = {t: {"login": None, "pet": {}, "verificado": False} for t in ("TRF4", "TJRS", "TJSC", "TJTO")}
_PROJUDI = {t: {"login": None, "pet": {}, "verificado": False} for t in ("TJPR", "TJGO")}

_SISTEMAS = {"e-SAJ": _ESAJ, "EPROC": _EPROC, "Projudi": _PROJUDI}


def resolve_route(tribunal: str | None, grau: str = "1") -> CourtRoute | None:
    if not tribunal or not tribunal.strip():
        return None
    sigla = tribunal.strip().upper()
    grau = grau if grau in ("1", "2") else "1"
    for sistema, fonte in _SISTEMAS.items():
        if sigla in fonte:
            cfg = fonte[sigla]
            return CourtRoute(
                tribunal=sigla,
                grau=grau,
                sistema=sistema,
                url_login=cfg.get("login"),
                url_peticionamento=cfg.get("pet", {}).get(grau),
                verificado=bool(cfg.get("verificado")),
            )
    # Default: PJe, sem URL (a confirmar no cadastro/registro).
    return CourtRoute(tribunal=sigla, grau=grau, sistema="PJe",
                      url_login=None, url_peticionamento=None, verificado=False)
```

Depois, em `court_systems.py`, substitua o corpo de `sistema_para_tribunal` por delegação (mantendo a assinatura e o docstring):

```python
# backend/app/capture/court_systems.py  (corpo da função)
def sistema_para_tribunal(tribunal: str | None) -> str | None:
    from app.capture.court_routing import resolve_route
    route = resolve_route(tribunal)
    return route.sistema if route is not None else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_court_routing.py tests/test_court_systems.py -v`
Expected: PASS (ambos — o registro cobre os mesmos casos do teste antigo)

- [ ] **Step 5: Verificar URLs reais e preencher o registro**

Para cada tribunal marcado `verificado=False`, confirme a URL de login e de peticionamento no site oficial (ex.: WebFetch em `https://www.tjXX.jus.br` / portal e-SAJ/PJe/eproc). Preencha `login`/`pet`/`verificado=True` quando confirmado. **Não invente URL**: se não confirmar, deixe `None`/`False` (o fallback manual cobre). Rode `ruff check .` e o pytest de novo.

- [ ] **Step 6: Commit**

```bash
git add backend/app/capture/court_routing.py backend/tests/test_court_routing.py backend/app/capture/court_systems.py
git commit -m "feat(routing): registro tribunal+grau -> sistema + URL de peticionamento"
```

---

### Task 2: Migração do cofre (sistema/grau/tipo) + store/load genéricos

Generaliza a credencial de sessão para carregar sistema/grau e vira base do chaveiro multi-tribunal.

**Files:**
- Modify: `backend/app/sor/models.py:231-254` (CredencialAssinatura)
- Create: `backend/alembic/versions/<rev>_credencial_sistema_grau_tipo.py`
- Modify: `backend/app/vault/service.py` (novos `store_court_session`/`load_court_session_payload`; `store_pje_session_reference`/`load_pje_session_payload` viram wrappers)
- Create: `backend/tests/test_vault_chaveiro.py`

**Interfaces:**
- Consumes: `resolve_route` (Task 1) — não obrigatório aqui, sistema vem por parâmetro.
- Produces:
  - `store_court_session(session, *, usuario_id: int, sistema: str, tribunal: str, grau: str, url_base: str, storage_state: dict) -> models.CredencialAssinatura`
  - `load_court_session_payload(session, *, credencial_id: int | None) -> dict | None` (payload inclui `sistema`, `grau`, `tribunal`, `url_base`, `storage_state`)
  - `find_active_session(session, *, usuario_id: int, sistema: str, tribunal: str, grau: str) -> models.CredencialAssinatura | None`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_vault_chaveiro.py
from app.sor import models
from app.vault.service import (
    find_active_session,
    load_court_session_payload,
    store_court_session,
)


def _usuario(db_session):
    esc = models.Escritorio(nome="Esc")
    db_session.add(esc)
    db_session.flush()
    u = models.Usuario(escritorio_id=esc.id, nome="Adv", email="a@e.com")
    db_session.add(u)
    db_session.flush()
    return u


def test_store_two_courts_and_find_the_right_one(db_session):
    u = _usuario(db_session)
    store_court_session(db_session, usuario_id=u.id, sistema="e-SAJ", tribunal="TJSP",
                        grau="1", url_base="https://esaj-treino.tjsp.jus.br",
                        storage_state={"cookies": [{"name": "x", "value": "s1"}]})
    store_court_session(db_session, usuario_id=u.id, sistema="PJe", tribunal="TRT2",
                        grau="1", url_base="https://pje-treino.trt2.jus.br",
                        storage_state={"cookies": [{"name": "y", "value": "s2"}]})

    esaj = find_active_session(db_session, usuario_id=u.id, sistema="e-SAJ", tribunal="TJSP", grau="1")
    assert esaj is not None and esaj.sistema == "e-SAJ" and esaj.tipo == "session"

    payload = load_court_session_payload(db_session, credencial_id=esaj.id)
    assert payload["sistema"] == "e-SAJ"
    assert payload["grau"] == "1"
    assert payload["storage_state"]["cookies"][0]["value"] == "s1"
    assert "s1" not in esaj.referencia_vault  # segredo não vaza no ref


def test_find_returns_none_when_no_session_for_court(db_session):
    u = _usuario(db_session)
    assert find_active_session(db_session, usuario_id=u.id, sistema="PJe", tribunal="TJMG", grau="1") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_vault_chaveiro.py -v`
Expected: FAIL (`ImportError: store_court_session` / coluna `sistema` inexistente)

- [ ] **Step 3: Add columns to the model**

Em `backend/app/sor/models.py`, na classe `CredencialAssinatura`, após `tribunal`:

```python
    sistema: Mapped[str | None] = mapped_column(String(20), nullable=True)
    grau: Mapped[str | None] = mapped_column(String(4), nullable=True)
    tipo: Mapped[str] = mapped_column(
        String(20), nullable=False, default="session", server_default=text("'session'")
    )
```

- [ ] **Step 4: Implement the store/load/find in the vault**

Em `backend/app/vault/service.py`, adicione (reaproveitando `_store_secret_reference`/`_load_secret_from_reference`/`_audit` já existentes):

```python
def store_court_session(
    session: Session, *, usuario_id: int, sistema: str, tribunal: str,
    grau: str, url_base: str, storage_state: dict,
) -> models.CredencialAssinatura:
    usuario = session.get(models.Usuario, usuario_id)
    if usuario is None:
        raise UsuarioNotFoundError("usuario nao encontrado")
    secret_payload = json.dumps(
        {"sistema": sistema, "tribunal": tribunal, "grau": grau,
         "url_base": url_base, "storage_state": storage_state},
        ensure_ascii=False, sort_keys=True,
    )
    credencial = models.CredencialAssinatura(
        usuario_id=usuario.id, provedor="CourtSession", tipo="session",
        sistema=sistema, tribunal=tribunal, grau=grau,
        referencia_vault=_store_secret_reference(
            session, usuario_id=usuario.id, provedor="CourtSession",
            secret=secret_payload, description="Sessao autenticada de tribunal; sem senha do usuario.",
        ),
        ativo=True,
    )
    session.add(credencial)
    session.flush()
    _audit(session, acao="sessao_tribunal_cadastrada", entidade="credencial_assinatura",
           entidade_id=credencial.id, ator=f"usuario:{usuario.id}",
           escritorio_id=usuario.escritorio_id, detalhe={"sistema": sistema, "tribunal": tribunal, "grau": grau})
    return credencial


def load_court_session_payload(session: Session, *, credencial_id: int | None) -> dict | None:
    if credencial_id is None:
        return None
    credencial = session.get(models.CredencialAssinatura, credencial_id)
    if credencial is None:
        raise CredencialNotFoundError("credencial de assinatura nao encontrada")
    if credencial.tipo != "session":
        return None
    secret = _load_secret_from_reference(session, credencial.referencia_vault)
    try:
        payload = json.loads(secret)
    except json.JSONDecodeError as exc:
        raise VaultProviderError("payload de sessao invalido no vault") from exc
    if not isinstance(payload, dict) or not payload.get("url_base") or not payload.get("storage_state"):
        raise VaultProviderError("payload de sessao incompleto no vault")
    return payload


def find_active_session(
    session: Session, *, usuario_id: int, sistema: str, tribunal: str, grau: str,
) -> models.CredencialAssinatura | None:
    stmt = (
        select(models.CredencialAssinatura)
        .where(
            models.CredencialAssinatura.usuario_id == usuario_id,
            models.CredencialAssinatura.tipo == "session",
            models.CredencialAssinatura.ativo.is_(True),
            models.CredencialAssinatura.sistema == sistema,
            models.CredencialAssinatura.tribunal == tribunal,
            models.CredencialAssinatura.grau == grau,
        )
        .order_by(models.CredencialAssinatura.id.desc())
    )
    return session.scalars(stmt).first()
```

Depois, reduza `store_pje_session_reference` a um wrapper (retrocompat com testes/endpoint atuais):

```python
def store_pje_session_reference(session, *, usuario_id, tribunal, url_base, storage_state):
    return store_court_session(session, usuario_id=usuario_id, sistema="PJe",
                               tribunal=tribunal, grau="1", url_base=url_base, storage_state=storage_state)


def load_pje_session_payload(session, *, credencial_id):
    return load_court_session_payload(session, credencial_id=credencial_id)
```

- [ ] **Step 5: Create the Alembic migration**

```python
# backend/alembic/versions/<rev>_credencial_sistema_grau_tipo.py
"""credencial: sistema/grau/tipo + backfill PJeSession->CourtSession"""
from alembic import op
import sqlalchemy as sa

revision = "<rev>"
down_revision = "<prev>"  # preencher com o head atual: alembic heads
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("credencial_assinatura", sa.Column("sistema", sa.String(20), nullable=True))
    op.add_column("credencial_assinatura", sa.Column("grau", sa.String(4), nullable=True))
    op.add_column("credencial_assinatura", sa.Column("tipo", sa.String(20), nullable=False, server_default="session"))
    op.execute("update credencial_assinatura set provedor='CourtSession', tipo='session', sistema='PJe' where provedor='PJeSession'")


def downgrade() -> None:
    op.drop_column("credencial_assinatura", "tipo")
    op.drop_column("credencial_assinatura", "grau")
    op.drop_column("credencial_assinatura", "sistema")
```

Descubra `down_revision` com `./.venv/Scripts/alembic.exe heads` e ajuste o `<rev>`/`<prev>`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_vault_chaveiro.py tests/test_pje_vault_job.py -v`
Expected: PASS (o wrapper mantém `test_pje_vault_job.py` verde)

- [ ] **Step 7: Commit**

```bash
git add backend/app/sor/models.py backend/app/vault/service.py backend/tests/test_vault_chaveiro.py backend/alembic/versions/
git commit -m "feat(vault): cofre multi-tribunal com sistema/grau/tipo e busca por tribunal"
```

---

### Task 3: Persistência file-backed do provider localdev

Impede perder a sessão se o backend reiniciar no meio da demo.

**Files:**
- Modify: `backend/app/vault/service.py` (`_LOCALDEV_SECRETS` → arquivo)
- Modify: `backend/app/settings.py` (caminho do arquivo, opcional via env)
- Create: `backend/tests/test_vault_localdev_persist.py`

**Interfaces:**
- Consumes: `store_court_session`/`load_court_session_payload` (Task 2)
- Produces: comportamento — segredos localdev sobrevivem a um novo processo (arquivo JSON fora do git).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_vault_localdev_persist.py
import importlib

from app.sor import models
from app.vault import service


def _usuario(db_session):
    esc = models.Escritorio(nome="Esc"); db_session.add(esc); db_session.flush()
    u = models.Usuario(escritorio_id=esc.id, nome="Adv", email="a@e.com")
    db_session.add(u); db_session.flush()
    return u


def test_localdev_secret_survives_module_reload(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("CAUSOR_VAULT_LOCALDEV_PATH", str(tmp_path / "vault.json"))
    importlib.reload(service)
    u = _usuario(db_session)
    cred = service.store_court_session(db_session, usuario_id=u.id, sistema="PJe",
        tribunal="TJMG", grau="1", url_base="https://pje-treino.tjmg.jus.br",
        storage_state={"cookies": [{"name": "z", "value": "keep-me"}]})
    cred_id = cred.id

    importlib.reload(service)  # simula reinício do processo
    payload = service.load_court_session_payload(db_session, credencial_id=cred_id)
    assert payload["storage_state"]["cookies"][0]["value"] == "keep-me"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_vault_localdev_persist.py -v`
Expected: FAIL (dict em memória some no reload)

- [ ] **Step 3: Make localdev store file-backed**

Em `backend/app/vault/service.py`, substitua o dict global por leitura/escrita em arquivo:

```python
import os
from pathlib import Path

_LOCALDEV_PATH = Path(os.getenv("CAUSOR_VAULT_LOCALDEV_PATH", ".causor-vault-localdev.json"))


def _localdev_load() -> dict[str, str]:
    if _LOCALDEV_PATH.exists():
        try:
            return json.loads(_LOCALDEV_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _localdev_save(data: dict[str, str]) -> None:
    _LOCALDEV_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
```

No ramo `provider == "localdev"` de `_store_secret_reference`:

```python
    if provider == "localdev":
        reference = _reference_for(usuario_id, provedor, secret)
        data = _localdev_load(); data[reference] = secret; _localdev_save(data)
        return reference
```

E em `_load_secret_from_reference` para `localdev://`:

```python
    if reference.startswith("localdev://"):
        data = _localdev_load()
        try:
            return data[reference]
        except KeyError as exc:
            raise VaultProviderError(
                "segredo localdev nao esta no arquivo; recadastre a sessao assistida"
            ) from exc
```

Adicione o arquivo ao `.gitignore` (`.causor-vault-localdev.json`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_vault_localdev_persist.py tests/test_pje_vault_job.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/vault/service.py backend/tests/test_vault_localdev_persist.py .gitignore
git commit -m "feat(vault): persistencia file-backed do provider localdev (sobrevive a restart)"
```

---

### Task 4: Interface FilingDriver + SandboxDriver + dispatch

Um driver por sistema atrás de uma interface; a demo usa o SandboxDriver determinístico.

**Files:**
- Create: `backend/app/connectors/drivers.py`
- Create: `backend/app/connectors/sandbox_driver.py`
- Create: `backend/tests/test_filing_drivers.py`
- Modify: `backend/app/settings.py` (flag `filing_mode`)

**Interfaces:**
- Consumes: `PjeAssistedConnector.prepare_filing(package, *, submit)` (existente), `PjeFilingCheckpoint`/`PjeFilingPackage`.
- Produces:
  - `class FilingDriver(Protocol)` com `sistema: str` e `prepare_filing(self, package, *, submit: bool) -> PjeFilingCheckpoint`
  - `get_filing_driver(sistema: str, *, mode: str) -> FilingDriver` — `mode="sandbox"` → `SandboxDriver(sistema)`; `mode="real"` → `PjeDriver` p/ PJe, `UnsupportedFilingSystemError` p/ demais.
  - `class SandboxDriver` — `prepare_filing` retorna `checkpoint="protocolado"`, `irreversible=True`, evidence com `protocolo`, `comprovante_url`, `states`, `screenshots`.
  - `UnsupportedFilingSystemError(RuntimeError)`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_filing_drivers.py
import pytest

from app.connectors.drivers import (
    UnsupportedFilingSystemError,
    get_filing_driver,
)
from app.connectors.pje.connector import PjeFilingPackage


def _package(sistema_numero="0000001-00.2024.8.26.0100"):
    return PjeFilingPackage(
        peticao_id=1, processo_id=1, numero_processo=sistema_numero,
        tribunal="TJSP", orgao_julgador="1a Vara", tipo_peticao="Manifestacao",
        conteudo="minuta", credencial_id=7,
    )


def test_sandbox_driver_returns_protocol_deterministically():
    driver = get_filing_driver("e-SAJ", mode="sandbox")
    checkpoint = driver.prepare_filing(_package(), submit=True)
    assert checkpoint.checkpoint == "protocolado"
    assert checkpoint.irreversible is True
    assert checkpoint.evidence["protocolo"]  # número presente
    assert checkpoint.evidence["sistema"] == "e-SAJ"
    assert checkpoint.evidence["states"]  # passos do agente
    # determinístico: mesmo processo -> mesmo protocolo
    again = get_filing_driver("e-SAJ", mode="sandbox").prepare_filing(_package(), submit=True)
    assert again.evidence["protocolo"] == checkpoint.evidence["protocolo"]


def test_real_mode_rejects_system_without_driver():
    with pytest.raises(UnsupportedFilingSystemError):
        get_filing_driver("e-SAJ", mode="real")


def test_real_mode_pje_returns_pje_driver():
    driver = get_filing_driver("PJe", mode="real")
    assert driver.sistema == "PJe"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_filing_drivers.py -v`
Expected: FAIL (`ModuleNotFoundError: app.connectors.drivers`)

- [ ] **Step 3: Implement the sandbox driver**

```python
# backend/app/connectors/sandbox_driver.py
"""Driver determinístico de homologação (Causor Sandbox).

NÃO é protocolo real. Renderiza os passos e um comprovante rotulado com o sistema
resolvido, para a demo mostrar o fluxo autônomo ponta a ponta sem risco de portal
real quebrando ao vivo.
"""
from __future__ import annotations

from hashlib import sha256

from app.connectors.pje.connector import PjeFilingCheckpoint, PjeFilingPackage

_STATES = ["session_ok", "processo_localizado", "peticionamento_aberto",
           "minuta_anexada", "assinado", "protocolado"]


class SandboxDriver:
    def __init__(self, sistema: str) -> None:
        self.sistema = sistema

    def prepare_filing(self, package: PjeFilingPackage, *, submit: bool = False) -> PjeFilingCheckpoint:
        digest = sha256(f"{self.sistema}:{package.numero_processo}".encode()).hexdigest()[:8].upper()
        protocolo = f"SANDBOX-{self.sistema.replace('-', '')}-{digest}"
        evidence = {
            "sandbox": True,
            "sistema": self.sistema,
            "processo": package.numero_processo,
            "tribunal": package.tribunal,
            "tipo_peticao": package.tipo_peticao,
            "credencial_id": package.credencial_id,
            "states": list(_STATES),
            "screenshots": [f"sandbox://{self.sistema}/{s}.png" for s in _STATES],
            "protocolo": protocolo,
            "comprovante_url": f"sandbox://comprovante/{protocolo}.pdf",
        }
        if not submit:
            ready = dict(evidence)
            ready["states"] = _STATES[:-2]  # para antes de assinar/protocolar
            ready.pop("protocolo"); ready.pop("comprovante_url")
            return PjeFilingCheckpoint(checkpoint="ready_to_sign", modo="causor_sandbox",
                                       irreversible=False, evidence=ready)
        return PjeFilingCheckpoint(checkpoint="protocolado", modo="causor_sandbox",
                                   irreversible=True, evidence=evidence)
```

```python
# backend/app/connectors/drivers.py
"""Interface única de driver de protocolo + dispatch por sistema."""
from __future__ import annotations

from typing import Protocol

from app.connectors.pje.connector import PjeAssistedConnector, PjeFilingCheckpoint, PjeFilingPackage
from app.connectors.sandbox_driver import SandboxDriver


class UnsupportedFilingSystemError(RuntimeError):
    """Sistema sem driver real (fora do modo sandbox)."""


class FilingDriver(Protocol):
    sistema: str
    def prepare_filing(self, package: PjeFilingPackage, *, submit: bool) -> PjeFilingCheckpoint: ...


class PjeDriver:
    sistema = "PJe"
    def __init__(self) -> None:
        self._connector = PjeAssistedConnector()
    def prepare_filing(self, package: PjeFilingPackage, *, submit: bool = False) -> PjeFilingCheckpoint:
        return self._connector.prepare_filing(package, submit=submit)


def get_filing_driver(sistema: str, *, mode: str) -> FilingDriver:
    if mode == "sandbox":
        return SandboxDriver(sistema)
    if sistema == "PJe":
        return PjeDriver()
    raise UnsupportedFilingSystemError(f"sem conector real para {sistema}; use sandbox ou registre manual")
```

Em `backend/app/settings.py`, adicione o campo (padrão sandbox p/ demo):

```python
    filing_mode: str = "sandbox"  # "sandbox" | "real"  (env CAUSOR_FILING_MODE)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_filing_drivers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/connectors/drivers.py backend/app/connectors/sandbox_driver.py backend/tests/test_filing_drivers.py backend/app/settings.py
git commit -m "feat(protocolo): interface FilingDriver + SandboxDriver deterministico + dispatch"
```

---

### Task 5: Protocolo roteado — generaliza `run_pje_protocol_job`

Remove o hard-stop PJe, resolve a sessão certa no cofre e despacha o driver do sistema.

**Files:**
- Modify: `backend/app/queue/jobs.py:388-537` (`run_pje_protocol_job`)
- Create: `backend/tests/test_protocolo_roteado.py`

**Interfaces:**
- Consumes: `resolve_route` (T1), `find_active_session`/`load_court_session_payload` (T2), `get_filing_driver` (T4), `settings.filing_mode`.
- Produces: `run_pje_protocol_job` passa a aceitar `usuario_id: int | None = None` (para achar a sessão) e resolve `credencial_id` sozinho quando não vier; mantém o parâmetro `connector` (seam de teste) sobrepondo o driver.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_protocolo_roteado.py
from app.queue.jobs import run_pje_protocol_job
from app.sor import models
from app.vault.service import store_court_session


def _seed(db_session, *, tribunal, sistema):
    esc = models.Escritorio(nome="Esc"); db_session.add(esc); db_session.flush()
    u = models.Usuario(escritorio_id=esc.id, nome="Adv", email="a@e.com"); db_session.add(u); db_session.flush()
    proc = models.Processo(escritorio_id=esc.id, numero="0000001-00.2024.8.26.0100",
                           tribunal=tribunal, sistema=sistema); db_session.add(proc); db_session.flush()
    pet = models.Peticao(escritorio_id=esc.id, processo_id=proc.id, tipo="Manifestacao",
                         conteudo="minuta", status="aprovada", aprovada_por=u.id)
    db_session.add(pet); db_session.flush()
    return u, pet


def test_esaj_petition_protocols_via_sandbox(db_session):
    u, pet = _seed(db_session, tribunal="TJSP", sistema="e-SAJ")
    store_court_session(db_session, usuario_id=u.id, sistema="e-SAJ", tribunal="TJSP",
                        grau="1", url_base="https://esaj-treino.tjsp.jus.br",
                        storage_state={"cookies": [{"name": "x", "value": "s"}]})

    job = run_pje_protocol_job(db_session, pet.id, usuario_id=u.id, submit=True, filing_mode="sandbox")

    assert job.status == "completed"
    assert job.resultado["sistema"] == "e-SAJ"
    assert job.resultado["protocolo"].startswith("SANDBOX-")
    db_session.refresh(pet)
    assert pet.status == "protocolada"
    assert "s" not in str(job.resultado)  # cookie não vaza


def test_missing_session_fails_clearly(db_session):
    u, pet = _seed(db_session, tribunal="TJMG", sistema="PJe")
    job = run_pje_protocol_job(db_session, pet.id, usuario_id=u.id, submit=True, filing_mode="sandbox")
    assert job.status == "failed"
    assert "conecte" in (job.erro or "").lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_protocolo_roteado.py -v`
Expected: FAIL (hard-stop `processo nao esta marcado como PJe` e/ou assinatura de parâmetro)

- [ ] **Step 3: Generalize the job**

Em `backend/app/queue/jobs.py`, na função `run_pje_protocol_job`:

1. **Remova** o hard-stop (linhas ~402-403):

```python
    # REMOVER:
    # if (peticao.processo.sistema or "").strip().lower() != "pje":
    #     raise UnsupportedFilingSystemError("processo nao esta marcado como PJe")
```

2. **Adicione parâmetros** `usuario_id: int | None = None`, `filing_mode: str | None = None` à assinatura.

3. **Resolva sistema/grau/sessão** logo após validar `processo.tribunal` (o `grau` sai do processo se existir, senão `"1"`):

```python
    from app.capture.court_routing import resolve_route
    from app.connectors.drivers import get_filing_driver, UnsupportedFilingSystemError as _Unsup
    from app.vault.service import find_active_session, load_court_session_payload
    from app.settings import settings as _settings

    grau = getattr(processo, "grau", None) or "1"
    route = resolve_route(processo.tribunal, grau)
    sistema = (processo.sistema or (route.sistema if route else None) or "PJe")
    mode = filing_mode or _settings.filing_mode

    if credencial_id is None and usuario_id is not None:
        sess = find_active_session(session, usuario_id=usuario_id, sistema=sistema,
                                   tribunal=processo.tribunal, grau=grau)
        if sess is None:
            raise PjeConnectorError(
                f"conecte o {processo.tribunal} ({sistema} · {grau}º grau) no cofre antes de protocolar"
            )
        credencial_id = sess.id
```

4. **Troque** os `"sistema": "PJe"` cravados por `sistema`; troque `PjeAssistedConnector()` pelo dispatch:

```python
    driver = connector or get_filing_driver(sistema, mode=mode)
    # ... e onde carregava a sessão:
    session_payload = load_court_session_payload(session, credencial_id=credencial_id)
    # ... checkpoint = driver.prepare_filing(package, submit=submit)
```

5. Envolva o dispatch para converter `_Unsup` em `PjeConnectorError` (fica no mesmo `except` que já reverte o status).

**Cuidado (não vazar segredo):** mantenha o `payload`/`resultado` sem `storage_state` (só metadados), como já é hoje.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_protocolo_roteado.py tests/test_pje_vault_job.py -v`
Expected: PASS (o seam `connector=` mantém `test_pje_vault_job` verde; ele passa `credencial_id` explícito, então não cai no ramo de resolução automática)

- [ ] **Step 5: Commit**

```bash
git add backend/app/queue/jobs.py backend/tests/test_protocolo_roteado.py
git commit -m "feat(protocolo): roteamento por sistema + resolucao automatica de sessao do cofre"
```

---

### Task 6: Endpoints — captura de sessão pela UI + consulta de rota

Tira a captura do CLI e expõe a resolução de rota para o modal.

**Files:**
- Modify: `backend/app/api/main.py` (novos endpoints; generaliza `cadastrar_sessao_pje`)
- Modify: `backend/app/api/schemas.py` (novos requests/outputs)
- Create: `backend/tests/test_api_sessao_tribunal.py`

**Interfaces:**
- Consumes: `capture_pje_storage_state` (existente), `resolve_route` (T1), `store_court_session` (T2).
- Produces:
  - `GET /court-routing?tribunal=&grau=` → `{sistema, url_login, url_peticionamento, verificado}`
  - `POST /usuarios/{id}/sessoes-tribunal/capturar` body `{tribunal, grau}` → captura headed local, salva sessão, retorna `CredencialAssinaturaOut`
  - `CredencialAssinaturaOut` ganha `sistema`, `grau`, `tipo`.

- [ ] **Step 1: Write the failing test** (usa o TestClient já usado em `test_api.py`; injeta um capturador fake por `app.dependency_overrides` ou monkeypatch do símbolo importado)

```python
# backend/tests/test_api_sessao_tribunal.py
from app.api import main as api_main


def test_court_routing_endpoint_resolves_tjsp(client):
    resp = client.get("/court-routing", params={"tribunal": "TJSP", "grau": "1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["sistema"] == "e-SAJ"
    assert "esaj.tjsp.jus.br" in body["url_peticionamento"]


def test_capturar_sessao_stores_session(client, monkeypatch):
    # não abre browser de verdade no teste
    monkeypatch.setattr(api_main, "capture_pje_storage_state",
                        lambda **kw: {"cookies": [{"name": "x", "value": "s"}]})
    usuario_id = api_main_seed_usuario(client)  # helper do teste (ver test_api.py)
    resp = client.post(f"/usuarios/{usuario_id}/sessoes-tribunal/capturar",
                       json={"tribunal": "TJSP", "grau": "1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["sistema"] == "e-SAJ"
    assert body["tipo"] == "session"
```

> Nota de implementação do teste: siga o padrão de `test_api.py` para a fixture `client` e para criar/autenticar um usuário; reaproveite o helper existente em vez de `api_main_seed_usuario` (placeholder acima) — leia `test_api.py` primeiro.

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_api_sessao_tribunal.py -v`
Expected: FAIL (rotas 404)

- [ ] **Step 3: Add schemas**

Em `backend/app/api/schemas.py`:

```python
class CourtRoutingOut(BaseModel):
    sistema: str
    url_login: str | None
    url_peticionamento: str | None
    verificado: bool


class CapturarSessaoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tribunal: str = Field(min_length=2, max_length=50)
    grau: str = Field(default="1", pattern="^[12]$")
```

E em `CredencialAssinaturaOut`, acrescente `sistema: str | None = None`, `grau: str | None = None`, `tipo: str | None = None`.

- [ ] **Step 4: Add endpoints**

Em `backend/app/api/main.py` (imports: `resolve_route`, `store_court_session`, `capture_pje_storage_state`, `CourtRoutingOut`, `CapturarSessaoRequest`):

```python
    @app.get("/court-routing", response_model=CourtRoutingOut)
    def consultar_rota(tribunal: str, grau: str = "1"):
        route = resolve_route(tribunal, grau)
        if route is None:
            raise HTTPException(status_code=404, detail="tribunal invalido")
        return CourtRoutingOut(sistema=route.sistema, url_login=route.url_login,
                               url_peticionamento=route.url_peticionamento, verificado=route.verificado)

    @app.post("/usuarios/{usuario_id}/sessoes-tribunal/capturar", response_model=CredencialAssinaturaOut)
    def capturar_sessao_tribunal(usuario_id: int, payload: CapturarSessaoRequest,
                                 session: Session = Depends(get_session),
                                 current: CurrentUser = Depends(get_current_user)):
        get_owned_or_404(session, models.Usuario, usuario_id, current)
        route = resolve_route(payload.tribunal, payload.grau)
        if route is None or not route.url_login:
            raise HTTPException(status_code=422, detail="tribunal sem URL de login no registro; verifique o cadastro")
        try:
            storage_state = capture_pje_storage_state(base_url=route.url_login)
            credencial = store_court_session(session, usuario_id=usuario_id, sistema=route.sistema,
                tribunal=route.tribunal, grau=payload.grau, url_base=route.url_login, storage_state=storage_state)
        except UsuarioNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (VaultProviderError, PjeSessionError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        session.commit(); session.refresh(credencial)
        return credencial
```

Importe `PjeSessionError` de `app.connectors.pje.session`. Mantenha o endpoint `POST /usuarios/{id}/pje-sessoes` como alias (não remova — `test_api.py` pode usar).

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_api_sessao_tribunal.py tests/test_api.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/main.py backend/app/api/schemas.py backend/tests/test_api_sessao_tribunal.py
git commit -m "feat(api): captura de sessao pela UI + consulta de rota do tribunal"
```

---

### Task 7: Protocolo async resolve sistema e usa usuario_id

Faz o endpoint de protocolo despachar qualquer sistema (sandbox) e passar o usuário para resolução de sessão.

**Files:**
- Modify: `backend/app/api/main.py:1246-1289` (`protocolar_peticao_async`)
- Create: `backend/tests/test_protocolar_async_multisistema.py`

**Interfaces:**
- Consumes: `run_pje_protocol_job` (T5, agora com `usuario_id`/`filing_mode`).
- Produces: `POST /peticoes/{id}/protocolar/async` roteia qualquer sistema (não mais 409 para não-PJe quando em sandbox).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_protocolar_async_multisistema.py
def test_esaj_petition_can_be_filed_via_async_in_sandbox(client, seed_esaj_aprovada):
    peticao_id, _ = seed_esaj_aprovada  # helper: cria processo TJSP/e-SAJ, minuta aprovada e sessão conectada
    resp = client.post(f"/peticoes/{peticao_id}/protocolar/async", json={})
    assert resp.status_code == 200
    job = resp.json()
    assert job["status"] in ("completed", "running")
```

> Nota: escreva `seed_esaj_aprovada` seguindo os helpers de `test_api.py`; conecte a sessão via `POST /usuarios/{id}/sessoes-tribunal/capturar` com `capture_pje_storage_state` monkeypatchado (como na Task 6).

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_protocolar_async_multisistema.py -v`
Expected: FAIL (409 "sistema nao-PJe sem conector dedicado")

- [ ] **Step 3: Update the endpoint**

Em `protocolar_peticao_async`, substitua o `if sistema == pje / else 409` por dispatch único passando `usuario_id`:

```python
        peticao = get_owned_or_404(session, models.Peticao, peticao_id, current)
        credencial_id = payload.credencial_id if payload is not None else None
        try:
            datajud_client = DatajudClient() if settings.datajud_api_key else _NoopDatajudClient()
            job = run_pje_protocol_job(
                session, peticao_id, credencial_id=credencial_id,
                usuario_id=current.usuario_id, datajud=datajud_client, submit=True,
            )
        except (PeticaoNotFoundError, CredencialNaoEncontradaError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ProcessoSemOrgaoError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (AlreadyFiledError, ApprovalRequiredError, CredencialInativaError,
                UnsupportedFilingSystemError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
```

(O caso "sessão não conectada" vira job `failed` com mensagem clara — a UI mostra o erro do job, não um 409.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_protocolar_async_multisistema.py tests/test_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/main.py backend/tests/test_protocolar_async_multisistema.py
git commit -m "feat(api): protocolo async roteia qualquer sistema via driver (sandbox na demo)"
```

---

### Task 8: Frontend — modal "Conectar tribunal" (sem CLI) + cliente de API

Substitui o comando de terminal por um botão real e mostra o sistema/URL resolvidos.

**Files:**
- Modify: `frontend/lib/api.ts` (tipos + funções)
- Modify: `frontend/app/components/VaultSection.tsx` (`ConectarPjeModal` → real)
- Create: `frontend/lib/api.court.test.ts` (Vitest, se houver setup; senão teste de componente conforme padrão do repo)

**Interfaces:**
- Consumes: `GET /court-routing`, `POST /usuarios/{id}/sessoes-tribunal/capturar` (T6).
- Produces (em `api.ts`):
  - `type CourtRouting = { sistema: string; url_login: string | null; url_peticionamento: string | null; verificado: boolean }`
  - `resolverRota(tribunal: string, grau: string): Promise<CourtRouting>`
  - `capturarSessaoTribunal(tribunal: string, grau: string, usuarioId?: number): Promise<CredencialAssinatura>`
  - `CredencialAssinatura` ganha `sistema?: string | null; grau?: string | null; tipo?: string | null`.

- [ ] **Step 1: Add API client functions**

Em `frontend/lib/api.ts`:

```typescript
export type CourtRouting = {
  sistema: string;
  url_login: string | null;
  url_peticionamento: string | null;
  verificado: boolean;
};

export async function resolverRota(tribunal: string, grau: string): Promise<CourtRouting> {
  const qs = new URLSearchParams({ tribunal, grau }).toString();
  return request<CourtRouting>(`/court-routing?${qs}`);
}

export async function capturarSessaoTribunal(
  tribunal: string, grau: string, usuarioId?: number
): Promise<CredencialAssinatura> {
  const id = usuarioId ?? (await resolverUsuarioAtual());
  return request<CredencialAssinatura>(`/usuarios/${id}/sessoes-tribunal/capturar`, {
    method: "POST",
    body: JSON.stringify({ tribunal, grau })
  });
}
```

Adicione `sistema?: string | null; grau?: string | null; tipo?: string | null;` ao tipo `CredencialAssinatura` (linha ~218).

- [ ] **Step 2: Rewrite the ConectarPjeModal (no CLI)**

Em `frontend/app/components/VaultSection.tsx`, substitua o corpo de `ConectarPjeModal` por: seletor de tribunal + grau, chamada a `resolverRota` (mostrando `sistema · URL`), botão "Conectar" que chama `capturarSessaoTribunal` e, ao concluir, fecha e recarrega. Mantenha o aviso de que a janela abre localmente. Exemplo do núcleo:

```tsx
const [tribunal, setTribunal] = useState("TJSP");
const [grau, setGrau] = useState("1");
const [rota, setRota] = useState<CourtRouting | null>(null);
const [busy, setBusy] = useState(false);
const toast = useToast();

useEffect(() => {
  let ok = true;
  resolverRota(tribunal, grau).then((r) => ok && setRota(r)).catch(() => ok && setRota(null));
  return () => { ok = false; };
}, [tribunal, grau]);

async function conectar() {
  setBusy(true);
  try {
    await capturarSessaoTribunal(tribunal, grau);
    toast({ kind: "success", title: "Tribunal conectado" });
    onConnected();  // recarrega a lista e fecha
  } catch (e) {
    toast({ kind: "error", title: e instanceof Error ? e.message : "Falha ao conectar" });
  } finally {
    setBusy(false);
  }
}
```

O cabeçalho mostra: `rota ? \`${rota.sistema} · ${rota.url_login ?? "URL não cadastrada"}\` : "…"`. Se `rota.url_login` for `null`, desabilite "Conectar" e explique que o tribunal precisa de URL verificada no registro.

Passe uma prop `onConnected` do `VaultSection` para o modal (que chama `reload()` + `setShowConnect(false)`).

- [ ] **Step 3: Run frontend checks**

Run (em `frontend/`): `pnpm test` e `pnpm build`
Expected: PASS / build ok

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api.ts frontend/app/components/VaultSection.tsx
git commit -m "feat(ui): conectar tribunal pela UI (sem CLI) mostrando sistema/URL resolvidos"
```

---

### Task 9: Frontend — protocolo sem escolha manual + evidência do agente

Remove o dropdown de credencial e mostra passos + protocolo + comprovante.

**Files:**
- Modify: `frontend/app/components/ProtocolarModal.tsx` (sem seleção manual)
- Modify: `frontend/app/views/ProtocolosView.tsx` (passos/screenshots/protocolo)

**Interfaces:**
- Consumes: `protocolarPeticaoAsync(peticaoId)` (sem credencial), `listarJobs` (evidence com `states`, `screenshots`, `protocolo`, `comprovante_url`, `sistema`).

- [ ] **Step 1: Simplify ProtocolarModal**

Remova o carregamento/seleção de credencial. O modal passa a: mostrar o processo/tipo, o **sistema de destino** (derivado de `processo.sistema`), o aviso do gate, e o botão "Confirmar e protocolar" que chama `onConfirm()` (sem `credencialId`). Ajuste a prop `onConfirm` para `() => void`. Se `processo?.sistema` estiver vazio, mostre aviso "sistema do processo não identificado".

- [ ] **Step 2: Show agent steps + protocol + comprovante in ProtocolosView**

Em `ProtocolosView.tsx`, no card do job, quando `job.resultado?.evidence?.states` existir, renderize a lista de passos (com o último = protocolado destacado), o `protocolo` (já mostrado como "Comprovante") e, se `evidence.comprovante_url`, um link. Adicione um badge `evidence.sistema` e, se `evidence.sandbox === true`, um rótulo discreto "homologação (sandbox)". Núcleo:

```tsx
const evidence = (job.resultado?.evidence ?? null) as Record<string, any> | null;
const states = Array.isArray(evidence?.states) ? (evidence!.states as string[]) : [];
const comprovanteUrl = typeof evidence?.comprovante_url === "string" ? evidence!.comprovante_url : null;
const sistema = typeof evidence?.sistema === "string" ? evidence!.sistema : null;
const isSandbox = evidence?.sandbox === true;
// render: {sistema && <span className="badge mono">{sistema}{isSandbox ? " · homologação" : ""}</span>}
// render: {states.length > 0 && <ol className="agentSteps">{states.map((s,i)=><li key={i}>{s}</li>)}</ol>}
// render: {comprovanteUrl && <a ...>Ver comprovante</a>}
```

- [ ] **Step 3: Run frontend checks**

Run (em `frontend/`): `pnpm test` e `pnpm build`
Expected: PASS / build ok

- [ ] **Step 4: Commit**

```bash
git add frontend/app/components/ProtocolarModal.tsx frontend/app/views/ProtocolosView.tsx
git commit -m "feat(ui): protocolo roteado sem escolha manual + passos/protocolo/comprovante do agente"
```

---

### Task 10: Cenário-semente da demo (multi-sistema)

Um estado inicial bom para a narrativa: processo(s) com intimação e minuta aprovada.

**Files:**
- Modify: `backend/app/sor/seed_demo.py`
- Modify: `backend/tests/test_seed_demo.py`

**Interfaces:**
- Consumes: modelos e o vault (`store_court_session`) para deixar um tribunal já conectado (opcional).
- Produces: `seed-demo` cria pelo menos um processo `TJSP/e-SAJ` com intimação e uma `peticao` `status="aprovada"` pronta para protocolar.

- [ ] **Step 1: Write the failing test**

```python
# adicionar em backend/tests/test_seed_demo.py
def test_seed_has_esaj_process_ready_to_file(db_session):
    from app.sor.seed_demo import seed_demo
    seed_demo(db_session)
    procs = db_session.query(models.Processo).filter(models.Processo.sistema == "e-SAJ").all()
    assert procs, "esperava ao menos um processo e-SAJ na semente"
    pet = db_session.query(models.Peticao).filter(models.Peticao.status == "aprovada").first()
    assert pet is not None
```

(Ajuste a assinatura de `seed_demo` conforme a existente — leia o arquivo antes; pode ser `seed_demo(session)` ou via engine.)

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_seed_demo.py -v`
Expected: FAIL (sem processo e-SAJ / minuta aprovada)

- [ ] **Step 3: Extend the seed**

Acrescente ao `seed_demo` um processo `numero` válido com `tribunal="TJSP"`, `sistema="e-SAJ"`, uma `intimacao` associada, e uma `peticao` `tipo="Manifestacao"`, `conteudo=<minuta demo>`, `status="aprovada"`, `aprovada_por=<usuario>`. Idempotente (não duplica em reexecução) — siga o padrão já usado no arquivo.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_seed_demo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/sor/seed_demo.py backend/tests/test_seed_demo.py
git commit -m "feat(demo): cenario-semente e-SAJ com intimacao e minuta aprovada"
```

---

### Task 11: Verificação ponta a ponta + suíte completa

Garante que o verde total e o fluxo da demo estão de pé.

**Files:** nenhum novo (verificação).

- [ ] **Step 1: Suíte e lint backend**

Run (em `backend/`): `./.venv/Scripts/python.exe -m pytest -q` e `./.venv/Scripts/python.exe -m ruff check .`
Expected: tudo verde.

- [ ] **Step 2: Frontend**

Run (em `frontend/`): `pnpm test` e `pnpm build`
Expected: verde / build ok.

- [ ] **Step 3: Smoke manual (localhost)**

Suba backend + frontend, rode `python -m app.cli seed-demo`, e no app: Conectar tribunal (TJSP) → aprovar minuta → protocolar → ver protocolo `SANDBOX-...` + passos + comprovante na ProtocolosView. Confirme que nenhum cookie/segredo aparece em logs ou no JSON do job.

- [ ] **Step 4: Commit (se houver ajustes de verificação)**

```bash
git add -A
git commit -m "chore: verificacao ponta a ponta do fluxo multi-tribunal"
```

---

## Self-Review

- **Spec coverage:** T1=registro (spec 3.1); T2=cofre multi-tribunal (3.2); T3=persistência localdev (3.2); T4=FilingDriver+Sandbox (3.4/3.6); T5=roteamento automático+dispatch (3.4/3.5); T6=captura pela UI+rota (3.3/5); T7=protocolo async multissistema (3.5/5); T8=modal conectar (3.3); T9=evidência+sem escolha manual (3.5/3.7); T10=semente (3.5 fluxo); T11=verificação (9). Cloud-cert real (3.4b) fica como **fase 2** (fora do plano dos 3 dias — o `request_signature` já é o seam; o Sandbox cumpre a assinatura na demo).
- **Placeholders:** os helpers de teste do frontend/API (`seed_esaj_aprovada`, fixture `client`) apontam explicitamente para reusar o padrão de `test_api.py` — o executor deve ler esse arquivo antes de escrever as tarefas 6/7. Sinalizado inline, não deixado vago.
- **Type consistency:** `CourtRoute`, `resolve_route`, `store_court_session`, `load_court_session_payload`, `find_active_session`, `get_filing_driver`, `SandboxDriver`, `run_pje_protocol_job(..., usuario_id, filing_mode)` usados com os mesmos nomes/assinaturas entre tarefas.

## Notas de escopo (3 dias)

Ordem de valor para a demo, se o tempo apertar: **T1 → T2 → T4 → T5 → T6 → T8 → T9 → T10** entregam o fluxo demoável ponta a ponta. **T3** (persistência) e **T7** (async multissistema) endurecem; **T11** valida. Cloud-cert real e conectores reais e-SAJ/EPROC/Projudi ficam para depois da reunião.
