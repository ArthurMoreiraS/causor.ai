# Leitura oficial dos autos via MNI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capturar autos íntegros pelo webservice SOAP oficial (MNI `consultarProcesso`), rodando no backend, plugado no pipeline de integridade do Plano 2, com fallback intacto para o agente local.

**Architecture:** `MniReaderDriver` implementa o contrato `CourtReaderDriver` existente; um executor in-backend dirige `record_initial_manifest` → `confirm_document_upload` → `finalize_capture` num job persistente `mni_capture`. O roteamento em `open_capture` escolhe `fonte="mni"` quando há credencial ativa + perfil de endpoint para a rota; senão mantém o comando de agente. Transporte SOAP artesanal (`httpx` + templates + `lxml` com parsing por `local-name()`).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy/Alembic, httpx, lxml, PostgreSQL/SQLite, Next.js/TypeScript/Vitest.

## Global Constraints

- Senha MNI nunca aparece em log, erro, `repr`, prompt ou resposta de API; vive no vault (`localdev`/`supabase`) e o SOR guarda só a referência.
- A prova de completude do Plano 2 não relaxa: duas enumerações com fingerprint idêntico, todo item verificado, magic bytes de PDF, não-PDF vira `unsupported_mime`.
- Sem perfil MNI registrado para `(tribunal, grau)` ⇒ rota indisponível (fail-closed, cai no agente). Perfis nascem `verificado=False`.
- Erro canônico nunca deixa captura/job em `running`.
- Testes live só com `RUN_MNI_LIVE=1`; nunca em CI.
- Comandos backend rodam de `/backend` com `.\.venv\Scripts\python.exe`.
- Novo código segue comentários/docstrings em pt-BR no padrão dos módulos vizinhos.

---

## File map

**Create**

- `backend/app/connectors/mni/__init__.py`
- `backend/app/connectors/mni/client.py`
- `backend/app/connectors/mni/profiles.py`
- `backend/app/connectors/mni/reader.py`
- `backend/app/connectors/mni/credentials.py`
- `backend/app/connectors/mni/executor.py`
- `backend/app/connectors/simulators/mni.py`
- `backend/app/api/mni_routes.py`
- `backend/alembic/versions/f1c8d4a7b2e9_mni_credencial_captura_fonte.py`
- `backend/tests/test_mni_client.py`
- `backend/tests/test_mni_profiles.py`
- `backend/tests/test_mni_reader.py`
- `backend/tests/test_mni_credentials.py`
- `backend/tests/test_mni_capture_flow.py`
- `backend/tests/test_mni_simulator_integration.py`
- `backend/tests/live/test_mni_live.py`
- `frontend/app/components/MniSection.tsx`
- `frontend/app/components/MniSection.test.tsx`

**Modify**

- `backend/app/connectors/errors.py` — `MniUnavailable`.
- `backend/app/vault/service.py` — wrappers públicos `store_generic_secret`/`load_secret`.
- `backend/app/sor/models.py` — `MniCredencial`, `CapturaAutos.fonte`.
- `backend/app/autos/service.py` — `resolve_capture_fonte` + branch em `open_capture`.
- `backend/app/autos/worker.py` — drain de jobs `mni_capture`.
- `backend/app/cli.py` — `process-autos-due` também drena MNI.
- `backend/app/api/autos_routes.py` — `CapturaOut.fonte`.
- `backend/app/api/main.py` — incluir router MNI.
- `backend/app/settings.py` — `mni_timeout_seconds`, `mni_download_batch`.
- `frontend/lib/api.ts` — tipos + 4 chamadas MNI + `fonte` em `AutosStatus`.
- `frontend/app/SettingsModal.tsx` — renderizar `MniSection`.
- `docs/estado.md` — registrar a capacidade.

---

### Task 1: Erro canônico + cliente SOAP MNI

**Files:**

- Modify: `backend/app/connectors/errors.py`
- Create: `backend/app/connectors/mni/__init__.py` (vazio)
- Create: `backend/app/connectors/mni/client.py`
- Create: `backend/tests/test_mni_client.py`
- Modify: `backend/app/settings.py`

**Interfaces:**

- Produces: `MniUnavailable(ConnectorError)` com `code="mni_unavailable"`, `retryable=True`, `requires_human=False`.
- Produces: `MniDocumentoMeta(id, tipo, descricao, data_hora, mimetype, nivel_sigilo, parent_id)`; `MniConsultaResult(sucesso, mensagem, documentos, conteudo_inline)`.
- Produces: `MniClient(url_endpoint, id_consultante, senha, timeout=None, transport=None)` com `consultar_processo(numero) -> MniConsultaResult` e `baixar_documentos(numero, ids) -> dict[str, bytes]`.
- Settings novos: `mni_timeout_seconds: float = 60.0`, `mni_download_batch: int = 5`.

- [ ] **Step 1: Write failing client tests**

```python
# backend/tests/test_mni_client.py
"""Cliente SOAP MNI: parsing tolerante, erros canonicos, senha nunca vaza."""

import base64

import httpx
import pytest

from app.connectors.errors import AccessDenied, DocumentDownloadFailed, MniUnavailable
from app.connectors.mni.client import MniClient

NS = 'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns2="http://www.cnj.jus.br/intercomunicacao-2.2.2"'

RESPOSTA_LISTA = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope {NS}><soap:Body>
  <ns2:consultarProcessoResposta>
    <sucesso>true</sucesso>
    <mensagem>Processo consultado com sucesso</mensagem>
    <processo>
      <dadosBasicos numero="00000000000000000000" classeProcessual="7" nivelSigilo="0"/>
      <documento idDocumento="SIM-DOC-001" tipoDocumento="1" dataHora="20260701120000"
                 mimetype="application/pdf" nivelSigilo="0" descricao="Peticao inicial"/>
      <documento idDocumento="SIM-DOC-002" tipoDocumento="4" dataHora="20260702090000"
                 mimetype="application/pdf" nivelSigilo="0" descricao="Decisao">
        <documentoVinculado idDocumento="SIM-DOC-003" tipoDocumento="9"
                            dataHora="20260702090500" mimetype="application/pdf"
                            nivelSigilo="1" descricao="Anexo sigiloso"/>
      </documento>
    </processo>
  </ns2:consultarProcessoResposta>
</soap:Body></soap:Envelope>"""

PDF_B64 = base64.b64encode(b"%PDF-1.4\n%SIM-DOC-001\n%%EOF\n").decode("ascii")

RESPOSTA_CONTEUDO = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope {NS}><soap:Body>
  <ns2:consultarProcessoResposta>
    <sucesso>true</sucesso>
    <mensagem>ok</mensagem>
    <processo>
      <documento idDocumento="SIM-DOC-001" tipoDocumento="1" dataHora="20260701120000"
                 mimetype="application/pdf" nivelSigilo="0" descricao="Peticao inicial">
        <conteudo>{PDF_B64}</conteudo>
      </documento>
    </processo>
  </ns2:consultarProcessoResposta>
</soap:Body></soap:Envelope>"""

RESPOSTA_AUTH = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope {NS}><soap:Body>
  <ns2:consultarProcessoResposta>
    <sucesso>false</sucesso>
    <mensagem>Usuario ou senha invalidos</mensagem>
  </ns2:consultarProcessoResposta>
</soap:Body></soap:Envelope>"""


def _client(handler) -> MniClient:
    return MniClient(
        url_endpoint="https://mni.sim.jus.br/intercomunicacao",
        id_consultante="12345678900",
        senha="segredo-mni",
        transport=httpx.MockTransport(handler),
    )


def test_consultar_processo_parses_documents_and_nested_attachment():
    client = _client(lambda request: httpx.Response(200, content=RESPOSTA_LISTA.encode()))
    result = client.consultar_processo("0000000-00.2026.8.13.0000")
    assert result.sucesso is True
    ids = [d.id for d in result.documentos]
    assert ids == ["SIM-DOC-001", "SIM-DOC-002", "SIM-DOC-003"]
    anexo = result.documentos[2]
    assert anexo.parent_id == "SIM-DOC-002"
    assert anexo.nivel_sigilo == 1


def test_baixar_documentos_decodes_base64_content():
    client = _client(lambda request: httpx.Response(200, content=RESPOSTA_CONTEUDO.encode()))
    blobs = client.baixar_documentos("0000000-00.2026.8.13.0000", ["SIM-DOC-001"])
    assert blobs["SIM-DOC-001"].startswith(b"%PDF-")


def test_baixar_documentos_missing_content_raises_download_failed():
    client = _client(lambda request: httpx.Response(200, content=RESPOSTA_LISTA.encode()))
    with pytest.raises(DocumentDownloadFailed):
        client.baixar_documentos("0000000-00.2026.8.13.0000", ["SIM-DOC-001"])


def test_auth_failure_maps_to_access_denied():
    client = _client(lambda request: httpx.Response(200, content=RESPOSTA_AUTH.encode()))
    with pytest.raises(AccessDenied):
        client.consultar_processo("0000000-00.2026.8.13.0000")


def test_http_5xx_and_timeout_map_to_mni_unavailable():
    client = _client(lambda request: httpx.Response(503))
    with pytest.raises(MniUnavailable):
        client.consultar_processo("0000000-00.2026.8.13.0000")

    def _timeout(request):
        raise httpx.ConnectTimeout("boom")

    client = _client(_timeout)
    with pytest.raises(MniUnavailable):
        client.consultar_processo("0000000-00.2026.8.13.0000")


def test_senha_nunca_aparece_em_repr_nem_em_erros():
    client = _client(lambda request: httpx.Response(200, content=RESPOSTA_AUTH.encode()))
    assert "segredo-mni" not in repr(client)
    with pytest.raises(AccessDenied) as excinfo:
        client.consultar_processo("0000000-00.2026.8.13.0000")
    assert "segredo-mni" not in str(excinfo.value)


def test_request_envelope_contains_credentials_and_number():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content.decode()
        return httpx.Response(200, content=RESPOSTA_LISTA.encode())

    client = _client(handler)
    client.consultar_processo("0000000-00.2026.8.13.0000")
    assert "<ser:idConsultante>12345678900</ser:idConsultante>" in seen["body"]
    assert "00000000020268130000" in seen["body"]  # numero sanitizado (so digitos)
```

- [ ] **Step 2: Run and verify failure on import**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mni_client.py -v`

Expected: FAIL — `ModuleNotFoundError: app.connectors.mni` (e `MniUnavailable` inexistente).

- [ ] **Step 3: Implement error, settings and client**

Em `backend/app/connectors/errors.py`, após `SystemMigrated`:

```python
class MniUnavailable(ConnectorError):
    """Endpoint MNI fora do ar ou instável; retry automático é seguro."""

    code = "mni_unavailable"
    retryable = True
    requires_human = False
```

Em `backend/app/settings.py`, junto dos knobs de documento (linha ~128):

```python
    mni_timeout_seconds: float = 60.0  # timeout por chamada SOAP ao MNI
    mni_download_batch: int = 5  # documentos por chamada de conteudo
```

`backend/app/connectors/mni/__init__.py` vazio. `backend/app/connectors/mni/client.py`:

```python
"""Cliente SOAP do MNI (consultarProcesso, intercomunicação 2.2.2).

Transporte artesanal: envelope por template + parsing lxml por
``local-name()``, porque tribunais variam prefixo/namespace. Sem WSDL em
runtime — WSDL de tribunal quebrado não pode derrubar o cliente. A senha
nunca aparece em log, erro ou ``repr``.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from xml.sax.saxutils import escape

import httpx
from lxml import etree

from app.connectors.errors import (
    AccessDenied,
    DocumentDownloadFailed,
    LayoutUnknown,
    MniUnavailable,
)
from app.settings import settings

_AUTH_HINTS = ("senha", "autoriza", "credenci", "usuario", "usuário", "login")

_ENVELOPE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
    'xmlns:ser="http://www.cnj.jus.br/servico-intercomunicacao-2.2.2/">'
    "<soapenv:Header/><soapenv:Body><ser:consultarProcesso>"
    "<ser:idConsultante>{id_consultante}</ser:idConsultante>"
    "<ser:senhaConsultante>{senha}</ser:senhaConsultante>"
    "<ser:numeroProcesso>{numero}</ser:numeroProcesso>"
    "<ser:movimentos>false</ser:movimentos>"
    "<ser:incluirCabecalho>true</ser:incluirCabecalho>"
    "<ser:incluirDocumentos>{incluir_documentos}</ser:incluirDocumentos>"
    "{documentos}"
    "</ser:consultarProcesso></soapenv:Body></soapenv:Envelope>"
)


@dataclass(frozen=True)
class MniDocumentoMeta:
    id: str
    tipo: str | None
    descricao: str | None
    data_hora: str | None
    mimetype: str | None
    nivel_sigilo: int
    parent_id: str | None = None


@dataclass(frozen=True)
class MniConsultaResult:
    sucesso: bool
    mensagem: str
    documentos: tuple[MniDocumentoMeta, ...]
    conteudo_inline: bool


def _sanitize_numero(numero: str) -> str:
    digits = "".join(ch for ch in numero if ch.isdigit())
    if not digits:
        raise LayoutUnknown("numero de processo vazio apos sanitizacao")
    return digits


class MniClient:
    def __init__(
        self,
        *,
        url_endpoint: str,
        id_consultante: str,
        senha: str,
        timeout: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self._url = url_endpoint
        self._id = id_consultante
        self._senha = senha
        self._timeout = timeout or settings.mni_timeout_seconds
        self._transport = transport

    def __repr__(self) -> str:  # senha fora do repr, sempre
        return f"MniClient(url={self._url!r}, id_consultante={self._id!r})"

    # -- transporte -------------------------------------------------------

    def _post(self, body: str) -> bytes:
        try:
            with httpx.Client(transport=self._transport, timeout=self._timeout) as http:
                response = http.post(
                    self._url,
                    content=body.encode("utf-8"),
                    headers={
                        "Content-Type": "text/xml; charset=utf-8",
                        "SOAPAction": "consultarProcesso",
                    },
                )
        except httpx.HTTPError as exc:
            raise MniUnavailable(f"falha de transporte MNI: {type(exc).__name__}") from exc
        if response.status_code >= 500:
            raise MniUnavailable(f"MNI respondeu HTTP {response.status_code}")
        if response.status_code >= 400:
            raise AccessDenied(f"MNI recusou a chamada: HTTP {response.status_code}")
        return response.content

    def _call(self, numero: str, *, incluir_documentos: bool, ids: list[str] | None = None) -> etree._Element:
        documentos = "".join(
            f"<ser:documento>{escape(doc_id)}</ser:documento>" for doc_id in (ids or [])
        )
        body = _ENVELOPE.format(
            id_consultante=escape(self._id),
            senha=escape(self._senha),
            numero=_sanitize_numero(numero),
            incluir_documentos="true" if incluir_documentos else "false",
            documentos=documentos,
        )
        raw = self._post(body)
        try:
            root = etree.fromstring(raw)
        except etree.XMLSyntaxError as exc:
            raise LayoutUnknown("resposta MNI nao e XML valido") from exc
        faults = root.xpath("//*[local-name()='Fault']")
        if faults:
            code = faults[0].findtext("faultcode") or "soap-fault"
            raise LayoutUnknown(f"SOAP Fault do MNI: {code[:80]}")
        self._check_sucesso(root)
        return root

    def _check_sucesso(self, root: etree._Element) -> None:
        sucesso = root.xpath("//*[local-name()='sucesso']/text()")
        mensagem = (root.xpath("//*[local-name()='mensagem']/text()") or [""])[0]
        if sucesso and sucesso[0].strip().lower() != "true":
            safe = mensagem[:200]
            if any(hint in safe.casefold() for hint in _AUTH_HINTS):
                raise AccessDenied(f"MNI negou a consulta: {safe}")
            raise LayoutUnknown(f"MNI sem sucesso: {safe}")

    # -- operações --------------------------------------------------------

    def consultar_processo(self, numero: str) -> MniConsultaResult:
        root = self._call(numero, incluir_documentos=True)
        mensagem = (root.xpath("//*[local-name()='mensagem']/text()") or [""])[0]
        documentos: list[MniDocumentoMeta] = []
        conteudo_inline = False
        for node in root.xpath("//*[local-name()='documento']"):
            meta = self._parse_documento(node, parent_id=None)
            documentos.append(meta)
            if node.xpath("./*[local-name()='conteudo']"):
                conteudo_inline = True
            for vinculado in node.xpath("./*[local-name()='documentoVinculado']"):
                documentos.append(self._parse_documento(vinculado, parent_id=meta.id))
        return MniConsultaResult(
            sucesso=True,
            mensagem=mensagem[:200],
            documentos=tuple(documentos),
            conteudo_inline=conteudo_inline,
        )

    def baixar_documentos(self, numero: str, ids: list[str]) -> dict[str, bytes]:
        root = self._call(numero, incluir_documentos=True, ids=list(ids))
        blobs: dict[str, bytes] = {}
        for node in root.xpath("//*[local-name()='documento']"):
            doc_id = node.get("idDocumento")
            conteudo = node.xpath("./*[local-name()='conteudo']/text()")
            if doc_id in ids and conteudo:
                try:
                    blobs[doc_id] = base64.b64decode("".join(conteudo), validate=True)
                except Exception as exc:  # noqa: BLE001 - base64 invalido e falha de download
                    raise DocumentDownloadFailed(f"base64 invalido para {doc_id}") from exc
        missing = [doc_id for doc_id in ids if doc_id not in blobs]
        if missing:
            raise DocumentDownloadFailed(f"MNI nao devolveu teor de: {', '.join(missing[:5])}")
        return blobs

    @staticmethod
    def _parse_documento(node: etree._Element, *, parent_id: str | None) -> MniDocumentoMeta:
        doc_id = node.get("idDocumento")
        if not doc_id:
            raise LayoutUnknown("documento MNI sem idDocumento")
        try:
            nivel = int(node.get("nivelSigilo") or 0)
        except ValueError:
            nivel = 0
        return MniDocumentoMeta(
            id=doc_id,
            tipo=node.get("tipoDocumento"),
            descricao=node.get("descricao"),
            data_hora=node.get("dataHora"),
            mimetype=node.get("mimetype"),
            nivel_sigilo=nivel,
            parent_id=parent_id,
        )
```

Nota: `documentoVinculado` aninhado dentro de outro `documento` também é
capturado pelo xpath global `//documento`? Não — o xpath global pega apenas
elementos com local-name `documento`; os vinculados têm local-name
`documentoVinculado` e entram pelo loop aninhado. Sem duplicatas.

- [ ] **Step 4: Run client tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mni_client.py -q`

Expected: PASS (8 testes).

- [ ] **Step 5: Commit**

```powershell
git add backend/app/connectors/errors.py backend/app/connectors/mni backend/app/settings.py backend/tests/test_mni_client.py
git commit -m "feat(mni): SOAP client with canonical errors and leak-safe secrets"
```

---

### Task 2: Perfis de endpoint MNI (registry fail-closed)

**Files:**

- Create: `backend/app/connectors/mni/profiles.py`
- Create: `backend/tests/test_mni_profiles.py`

**Interfaces:**

- Produces: `MniEndpointProfile(tribunal, grau, url_endpoint, versao="2.2.2", verificado=False)`; `resolve_mni_profile(tribunal, grau) -> MniEndpointProfile | None`; `known_mni_profiles() -> list[MniEndpointProfile]`.

- [ ] **Step 1: Write failing profile tests**

```python
# backend/tests/test_mni_profiles.py
from app.connectors.mni.profiles import MniEndpointProfile, resolve_mni_profile


def test_resolve_known_profile_by_tribunal_and_grau():
    profile = resolve_mni_profile("TJMG", "1")
    assert profile is not None
    assert profile.url_endpoint.startswith("https://pje.tjmg.jus.br/")
    assert profile.verificado is False  # so o credenciamento real confere


def test_resolve_is_case_insensitive_and_fails_closed():
    assert resolve_mni_profile("tjmg", "1") is not None
    assert resolve_mni_profile("TJXX", "1") is None
    assert resolve_mni_profile("TJMG", "3") is None


def test_profile_is_immutable():
    profile = resolve_mni_profile("TJMG", "1")
    try:
        profile.url_endpoint = "https://x"  # type: ignore[misc]
        raised = False
    except AttributeError:
        raised = True
    assert raised
```

- [ ] **Step 2: Run and verify missing module**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mni_profiles.py -v`

Expected: FAIL on import.

- [ ] **Step 3: Implement registry**

```python
# backend/app/connectors/mni/profiles.py
"""Endpoints MNI por (tribunal, grau).

Padrão PJe: ``https://<host-do-grau>/pje/intercomunicacao``. Entradas nascem
``verificado=False`` — palpite forte a conferir no credenciamento; sem
entrada, o MNI está indisponível para a rota (fail-closed) e a captura cai
no agente local. Espelha o desenho best-effort de
``capture/court_routing.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MniEndpointProfile:
    tribunal: str
    grau: str
    url_endpoint: str
    versao: str = "2.2.2"
    verificado: bool = False


_PROFILES: dict[tuple[str, str], MniEndpointProfile] = {}


def _register(tribunal: str, grau: str, url_endpoint: str) -> None:
    key = (tribunal.upper(), grau)
    _PROFILES[key] = MniEndpointProfile(
        tribunal=tribunal.upper(), grau=grau, url_endpoint=url_endpoint
    )


# PJe estadual conferível contra court_routing (mesmos hosts por grau).
_register("TJMG", "1", "https://pje.tjmg.jus.br/pje/intercomunicacao")
_register("TJMG", "2", "https://pje2g.tjmg.jus.br/pje/intercomunicacao")
_register("TJDFT", "1", "https://pje.tjdft.jus.br/pje/intercomunicacao")
_register("TJDFT", "2", "https://pje2i.tjdft.jus.br/pje/intercomunicacao")
_register("TJBA", "1", "https://pje.tjba.jus.br/pje/intercomunicacao")
_register("TJBA", "2", "https://pje2g.tjba.jus.br/pje/intercomunicacao")
_register("TJPE", "1", "https://pje.tjpe.jus.br/1g/intercomunicacao")
_register("TJPE", "2", "https://pje.tjpe.jus.br/2g/intercomunicacao")

# Justica do Trabalho: padrao CSJT por grau.
for _n in range(1, 25):
    _register("TRT%d" % _n, "1", f"https://pje.trt{_n}.jus.br/primeirograu/intercomunicacao")
    _register("TRT%d" % _n, "2", f"https://pje.trt{_n}.jus.br/segundograu/intercomunicacao")


def resolve_mni_profile(tribunal: str | None, grau: str) -> MniEndpointProfile | None:
    if not tribunal or grau not in ("1", "2"):
        return None
    return _PROFILES.get((tribunal.strip().upper(), grau))


def known_mni_profiles() -> list[MniEndpointProfile]:
    return sorted(_PROFILES.values(), key=lambda p: (p.tribunal, p.grau))
```

- [ ] **Step 4: Run profile tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mni_profiles.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/connectors/mni/profiles.py backend/tests/test_mni_profiles.py
git commit -m "feat(mni): fail-closed endpoint profiles per tribunal/grau"
```

---

### Task 3: MniReaderDriver (contrato CourtReaderDriver)

**Files:**

- Create: `backend/app/connectors/mni/reader.py`
- Create: `backend/tests/test_mni_reader.py`

**Interfaces:**

- Consumes: `MniClient.consultar_processo`, `MniClient.baixar_documentos` (Task 1); `CourtTarget`, `CourtDocumentRef`, `CourtManifestSnapshot` de `app/connectors/contracts.py`.
- Produces: `MniReaderDriver(client)` com `sistema="MNI"`, `enumerate_documents(target) -> CourtManifestSnapshot`, `prefetch(target, refs) -> None`, `download_document(target, ref) -> bytes`.

- [ ] **Step 1: Write failing reader tests**

```python
# backend/tests/test_mni_reader.py
from datetime import date

import pytest

from app.connectors.contracts import CourtTarget
from app.connectors.errors import DocumentDownloadFailed
from app.connectors.mni.client import MniConsultaResult, MniDocumentoMeta
from app.connectors.mni.reader import MniReaderDriver

TARGET = CourtTarget(
    processo_instancia_id=1,
    processo_id=1,
    numero_processo="0000000-00.2026.8.13.0000",
    sistema="PJe",
    tribunal="TJMG",
    grau="1",
    url_base="https://pje.tjmg.jus.br",
)

_DOCS = (
    MniDocumentoMeta(id="SIM-DOC-001", tipo="1", descricao="Peticao inicial",
                     data_hora="20260701120000", mimetype="application/pdf", nivel_sigilo=0),
    MniDocumentoMeta(id="SIM-DOC-002", tipo="4", descricao="Decisao",
                     data_hora="20260702090000", mimetype="application/pdf", nivel_sigilo=0),
    MniDocumentoMeta(id="SIM-DOC-003", tipo="9", descricao="Anexo sigiloso",
                     data_hora="20260702090500", mimetype="application/pdf",
                     nivel_sigilo=1, parent_id="SIM-DOC-002"),
)


class FakeClient:
    def __init__(self):
        self.download_calls: list[list[str]] = []

    def consultar_processo(self, numero):
        return MniConsultaResult(
            sucesso=True, mensagem="ok", documentos=_DOCS, conteudo_inline=False
        )

    def baixar_documentos(self, numero, ids):
        self.download_calls.append(list(ids))
        return {doc_id: b"%PDF-1.4\n%" + doc_id.encode() + b"\n%%EOF\n" for doc_id in ids}


def test_enumerate_produces_complete_snapshot_with_stable_fingerprint():
    driver = MniReaderDriver(FakeClient())
    first = driver.enumerate_documents(TARGET)
    second = driver.enumerate_documents(TARGET)
    assert first.cursor_complete is True
    assert first.source_fingerprint == second.source_fingerprint
    assert [d.external_id for d in first.documentos] == [
        "SIM-DOC-001", "SIM-DOC-002", "SIM-DOC-003"
    ]
    assert first.documentos[2].sigiloso is True
    assert first.documentos[2].parent_external_id == "SIM-DOC-002"
    assert first.documentos[0].data_documento == date(2026, 7, 1)
    assert first.evidence["fonte"] == "mni"


def test_prefetch_batches_and_download_serves_from_cache():
    client = FakeClient()
    driver = MniReaderDriver(client, batch_size=2)
    snapshot = driver.enumerate_documents(TARGET)
    driver.prefetch(TARGET, snapshot.documentos)
    assert client.download_calls == [["SIM-DOC-001", "SIM-DOC-002"], ["SIM-DOC-003"]]
    data = driver.download_document(TARGET, snapshot.documentos[0])
    assert data.startswith(b"%PDF-")
    assert client.download_calls == [["SIM-DOC-001", "SIM-DOC-002"], ["SIM-DOC-003"]]


def test_download_without_prefetch_fetches_single_document():
    client = FakeClient()
    driver = MniReaderDriver(client)
    snapshot = driver.enumerate_documents(TARGET)
    driver.download_document(TARGET, snapshot.documentos[1])
    assert client.download_calls == [["SIM-DOC-002"]]


def test_download_failure_propagates_canonical_error():
    class FailingClient(FakeClient):
        def baixar_documentos(self, numero, ids):
            raise DocumentDownloadFailed("sem teor")

    driver = MniReaderDriver(FailingClient())
    snapshot = driver.enumerate_documents(TARGET)
    with pytest.raises(DocumentDownloadFailed):
        driver.download_document(TARGET, snapshot.documentos[0])
```

- [ ] **Step 2: Run and verify missing reader**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mni_reader.py -v`

Expected: FAIL on import.

- [ ] **Step 3: Implement driver**

```python
# backend/app/connectors/mni/reader.py
"""Driver de leitura MNI: contrato CourtReaderDriver sobre o cliente SOAP.

A enumeração vem inteira numa chamada (MNI não pagina); ``cursor_complete``
só é True com resposta ``sucesso``. O fingerprint cobre id/tipo/dataHora/
mimetype ordenados — mudança no conjunto entre as duas enumerações reprova a
captura no ``finalize_capture`` do Plano 2.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256

from app.connectors.contracts import (
    CourtDocumentRef,
    CourtManifestSnapshot,
    CourtTarget,
)
from app.connectors.mni.client import MniDocumentoMeta
from app.settings import settings


def _parse_data(data_hora: str | None) -> date | None:
    if not data_hora or len(data_hora) < 8:
        return None
    try:
        return datetime.strptime(data_hora[:8], "%Y%m%d").date()
    except ValueError:
        return None


class MniReaderDriver:
    sistema = "MNI"

    def __init__(self, client, *, batch_size: int | None = None):
        self._client = client
        self._batch = batch_size or settings.mni_download_batch
        self._cache: dict[str, bytes] = {}

    def enumerate_documents(self, target: CourtTarget) -> CourtManifestSnapshot:
        result = self._client.consultar_processo(target.numero_processo)
        refs = tuple(
            self._to_ref(meta, ordem) for ordem, meta in enumerate(result.documentos, start=1)
        )
        fingerprint = sha256(
            "|".join(
                f"{m.id};{m.tipo};{m.data_hora};{m.mimetype}"
                for m in sorted(result.documentos, key=lambda m: m.id)
            ).encode("utf-8")
        ).hexdigest()
        return CourtManifestSnapshot(
            target=target,
            documentos=refs,
            cursor_complete=result.sucesso,
            source_fingerprint=f"sha256:{fingerprint}",
            captured_at=datetime.now(timezone.utc),
            evidence={
                "fonte": "mni",
                "documentos": len(refs),
                "conteudo_inline": result.conteudo_inline,
                "mensagem": result.mensagem,
            },
        )

    def prefetch(self, target: CourtTarget, refs: tuple[CourtDocumentRef, ...]) -> None:
        pending = [ref.external_id for ref in refs if ref.external_id not in self._cache]
        for start in range(0, len(pending), self._batch):
            batch = pending[start : start + self._batch]
            self._cache.update(self._client.baixar_documentos(target.numero_processo, batch))

    def download_document(self, target: CourtTarget, ref: CourtDocumentRef) -> bytes:
        if ref.external_id not in self._cache:
            self._cache.update(
                self._client.baixar_documentos(target.numero_processo, [ref.external_id])
            )
        return self._cache.pop(ref.external_id)

    @staticmethod
    def _to_ref(meta: MniDocumentoMeta, ordem: int) -> CourtDocumentRef:
        return CourtDocumentRef(
            external_id=meta.id,
            nome=(meta.descricao or meta.id)[:255],
            tipo=meta.tipo,
            ordem=ordem,
            data_documento=_parse_data(meta.data_hora),
            sigiloso=meta.nivel_sigilo > 0,
            mime_type=meta.mimetype,
            size_hint=None,
            download_ref=meta.id,
            parent_external_id=meta.parent_id,
        )
```

- [ ] **Step 4: Run reader tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mni_reader.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/connectors/mni/reader.py backend/tests/test_mni_reader.py
git commit -m "feat(mni): CourtReaderDriver over the SOAP client with batched prefetch"
```

---

### Task 4: Modelo de dados — `mni_credencial` + `captura_autos.fonte`

**Files:**

- Modify: `backend/app/sor/models.py`
- Create: `backend/alembic/versions/f1c8d4a7b2e9_mni_credencial_captura_fonte.py`
- Create: `backend/tests/test_mni_credentials.py` (parte de modelo; cresce na Task 5)

**Interfaces:**

- Produces: `models.MniCredencial(escritorio_id, tribunal, id_consultante, referencia_vault, ativo, last_validated_at, created_by_usuario_id)`, unique `(escritorio_id, tribunal)`.
- Produces: `models.CapturaAutos.fonte: str` default `"agente"`.

- [ ] **Step 1: Write failing model tests**

```python
# backend/tests/test_mni_credentials.py
import pytest
from sqlalchemy.exc import IntegrityError

from app.sor import models


def test_mni_credencial_unique_por_escritorio_tribunal(db_session, seeded):
    db_session.add(models.MniCredencial(
        escritorio_id=seeded.escritorio_id, tribunal="TJMG",
        id_consultante="12345678900", referencia_vault="localdev://mni/x", ativo=True,
    ))
    db_session.flush()
    db_session.add(models.MniCredencial(
        escritorio_id=seeded.escritorio_id, tribunal="TJMG",
        id_consultante="98765432100", referencia_vault="localdev://mni/y", ativo=True,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_captura_autos_fonte_default_agente(db_session, seeded):
    instancia = db_session.query(models.ProcessoInstancia).first()
    capture = models.CapturaAutos(
        escritorio_id=seeded.escritorio_id,
        processo_instancia_id=instancia.id,
        generation=99,
        status="queued",
    )
    db_session.add(capture)
    db_session.flush()
    assert capture.fonte == "agente"
```

Nota: se o `seeded` do conftest não criar `ProcessoInstancia`, criar uma no
teste (processo + instancia mínimos) seguindo o padrão dos testes de autos
existentes (ver `tests/test_autos_capture.py` ou equivalente para o setup).

- [ ] **Step 2: Run and verify missing model**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mni_credentials.py -v`

Expected: FAIL — `MniCredencial` não existe / `fonte` não existe.

- [ ] **Step 3: Add models and migration**

Em `backend/app/sor/models.py`, após `CapturaAutos` (usar os mesmos imports já
presentes no módulo):

```python
class MniCredencial(TimestampMixin, Base):
    """Credencial de consulta MNI por (escritorio, tribunal).

    A senha vive no vault; aqui fica somente a referência. O mesmo
    credenciamento cobre 1º/2º grau — o endpoint por grau vem do perfil em
    ``connectors/mni/profiles.py``.
    """

    __tablename__ = "mni_credencial"
    __table_args__ = (
        UniqueConstraint("escritorio_id", "tribunal", name="uq_mni_credencial_tribunal"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(
        ForeignKey("escritorio.id"), nullable=False, index=True
    )
    tribunal: Mapped[str] = mapped_column(String(50), nullable=False)
    id_consultante: Mapped[str] = mapped_column(String(120), nullable=False)
    referencia_vault: Mapped[str] = mapped_column(String(255), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
```

Em `CapturaAutos`, após `error_code`:

```python
    fonte: Mapped[str] = mapped_column(String(10), nullable=False, default="agente")
```

Migração `backend/alembic/versions/f1c8d4a7b2e9_mni_credencial_captura_fonte.py`:

```python
"""mni credencial + captura fonte

Revision ID: f1c8d4a7b2e9
Revises: c9f7a1b5d4e3
Create Date: 2026-07-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1c8d4a7b2e9"
down_revision: Union[str, Sequence[str], None] = "c9f7a1b5d4e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mni_credencial",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escritorio_id", sa.Integer(), sa.ForeignKey("escritorio.id"), nullable=False, index=True),
        sa.Column("tribunal", sa.String(length=50), nullable=False),
        sa.Column("id_consultante", sa.String(length=120), nullable=False),
        sa.Column("referencia_vault", sa.String(length=255), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_usuario_id", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("escritorio_id", "tribunal", name="uq_mni_credencial_tribunal"),
    )
    op.add_column(
        "captura_autos",
        sa.Column("fonte", sa.String(length=10), nullable=False, server_default="agente"),
    )


def downgrade() -> None:
    op.drop_column("captura_autos", "fonte")
    op.drop_table("mni_credencial")
```

Conferir os nomes das colunas de `TimestampMixin` (`created_at`/`updated_at`)
contra outra migração recente (ex.: `c9f7a1b5d4e3_connector_validation.py`) e
copiar o mesmo padrão de server_default.

- [ ] **Step 4: Run model tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mni_credentials.py -q`

Expected: PASS (tabelas de teste vêm de `Base.metadata.create_all`).

- [ ] **Step 5: Commit**

```powershell
git add backend/app/sor/models.py backend/alembic/versions/f1c8d4a7b2e9_mni_credencial_captura_fonte.py backend/tests/test_mni_credentials.py
git commit -m "feat(mni): credential model and capture source column"
```

---

### Task 5: Credenciais no vault + rotas API `/mni/credenciais`

**Files:**

- Modify: `backend/app/vault/service.py`
- Create: `backend/app/connectors/mni/credentials.py`
- Create: `backend/app/api/mni_routes.py`
- Modify: `backend/app/api/main.py`
- Modify: `backend/tests/test_mni_credentials.py` (acrescenta serviço + rotas)

**Interfaces:**

- Produces em `vault/service.py`: `store_generic_secret(session, *, usuario_id, provedor, secret, description) -> str` e `load_secret(session, reference) -> str` (wrappers públicos dos helpers privados existentes).
- Produces em `credentials.py`: `store_mni_credencial(session, *, escritorio_id, usuario_id, tribunal, id_consultante, senha) -> MniCredencial`; `find_active_credencial(session, *, escritorio_id, tribunal) -> MniCredencial | None`; `deactivate_mni_credencial(session, *, credencial_id, escritorio_id) -> MniCredencial`; `load_credencial_senha(session, credencial) -> str`; `mark_validated(session, credencial) -> None`.
- API: `POST /mni/credenciais`, `GET /mni/credenciais`, `DELETE /mni/credenciais/{id}`, `POST /mni/credenciais/{id}/testar`.

- [ ] **Step 1: Extend tests with service + route expectations**

Acrescentar ao `backend/tests/test_mni_credentials.py`:

```python
from app.connectors.mni import credentials as mni_credentials


def test_store_keeps_senha_no_vault_e_fora_do_sor(db_session, seeded):
    cred = mni_credentials.store_mni_credencial(
        db_session,
        escritorio_id=seeded.escritorio_id,
        usuario_id=seeded.usuario_id,
        tribunal="TJMG",
        id_consultante="12345678900",
        senha="senha-mni-secreta",
    )
    assert cred.referencia_vault.startswith(("localdev://", "supabase-vault://"))
    assert "senha-mni-secreta" not in cred.referencia_vault
    assert mni_credentials.load_credencial_senha(db_session, cred) == "senha-mni-secreta"


def test_store_replaces_existing_row_for_same_tribunal(db_session, seeded):
    first = mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id, usuario_id=seeded.usuario_id,
        tribunal="TJMG", id_consultante="111", senha="a",
    )
    second = mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id, usuario_id=seeded.usuario_id,
        tribunal="TJMG", id_consultante="222", senha="b",
    )
    assert second.id == first.id  # upsert na unique (escritorio, tribunal)
    assert second.id_consultante == "222"
    assert second.ativo is True


def test_find_active_ignores_deactivated(db_session, seeded):
    cred = mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id, usuario_id=seeded.usuario_id,
        tribunal="TJBA", id_consultante="333", senha="c",
    )
    assert mni_credentials.find_active_credencial(
        db_session, escritorio_id=seeded.escritorio_id, tribunal="TJBA"
    ) is not None
    mni_credentials.deactivate_mni_credencial(
        db_session, credencial_id=cred.id, escritorio_id=seeded.escritorio_id
    )
    assert mni_credentials.find_active_credencial(
        db_session, escritorio_id=seeded.escritorio_id, tribunal="TJBA"
    ) is None


def test_api_cadastra_lista_mascarada_e_revoga(client):
    created = client.post("/mni/credenciais", json={
        "tribunal": "TJMG", "id_consultante": "12345678900", "senha": "s3nh4",
    })
    assert created.status_code == 200
    body = created.json()
    assert "senha" not in body
    assert body["id_consultante_mask"].startswith("123")
    assert "12345678900" != body["id_consultante_mask"]

    listed = client.get("/mni/credenciais")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    removed = client.delete(f"/mni/credenciais/{body['id']}")
    assert removed.status_code == 200
    assert client.get("/mni/credenciais").json()[0]["ativo"] is False
```

- [ ] **Step 2: Run and verify failures**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mni_credentials.py -v`

Expected: FAIL — módulo `credentials` e rotas inexistentes.

- [ ] **Step 3: Implement vault wrappers, service and routes**

Em `backend/app/vault/service.py`, após `_load_secret_from_reference`:

```python
def store_generic_secret(
    session: Session,
    *,
    usuario_id: int,
    provedor: str,
    secret: str,
    description: str,
) -> str:
    """Grava um segredo generico no provider configurado; devolve a referencia."""
    return _store_secret_reference(
        session,
        usuario_id=usuario_id,
        provedor=provedor,
        secret=secret,
        description=description,
    )


def load_secret(session: Session, reference: str) -> str:
    """Recupera um segredo pela referencia (localdev/supabase)."""
    return _load_secret_from_reference(session, reference)
```

`backend/app/connectors/mni/credentials.py`:

```python
"""Credenciais MNI: segredo no vault, referência no SOR, auditoria sempre."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.sor import models
from app.vault.service import load_secret, store_generic_secret


class MniCredencialNotFound(RuntimeError):
    pass


def _audit(session, *, acao, credencial, ator):
    session.add(models.AuditLog(
        escritorio_id=credencial.escritorio_id,
        ator=ator,
        acao=acao,
        entidade="mni_credencial",
        entidade_id=credencial.id,
        detalhe={"tribunal": credencial.tribunal},
    ))


def store_mni_credencial(
    session: Session,
    *,
    escritorio_id: int,
    usuario_id: int | None,
    tribunal: str,
    id_consultante: str,
    senha: str,
) -> models.MniCredencial:
    tribunal = tribunal.strip().upper()
    referencia = store_generic_secret(
        session,
        usuario_id=usuario_id or 0,
        provedor=f"mni-{tribunal.lower()}",
        secret=senha,
        description=f"Senha de consulta MNI ({tribunal}).",
    )
    existing = session.scalars(
        select(models.MniCredencial).where(
            models.MniCredencial.escritorio_id == escritorio_id,
            models.MniCredencial.tribunal == tribunal,
        )
    ).first()
    if existing is not None:
        existing.id_consultante = id_consultante
        existing.referencia_vault = referencia
        existing.ativo = True
        existing.last_validated_at = None
        credencial = existing
        acao = "mni_credencial_atualizada"
    else:
        credencial = models.MniCredencial(
            escritorio_id=escritorio_id,
            tribunal=tribunal,
            id_consultante=id_consultante,
            referencia_vault=referencia,
            ativo=True,
            created_by_usuario_id=usuario_id,
        )
        session.add(credencial)
        acao = "mni_credencial_cadastrada"
    session.flush()
    _audit(session, acao=acao, credencial=credencial,
           ator=f"usuario:{usuario_id}" if usuario_id else "system")
    return credencial


def find_active_credencial(
    session: Session, *, escritorio_id: int, tribunal: str | None
) -> models.MniCredencial | None:
    if not tribunal:
        return None
    return session.scalars(
        select(models.MniCredencial).where(
            models.MniCredencial.escritorio_id == escritorio_id,
            models.MniCredencial.tribunal == tribunal.strip().upper(),
            models.MniCredencial.ativo.is_(True),
        )
    ).first()


def deactivate_mni_credencial(
    session: Session, *, credencial_id: int, escritorio_id: int
) -> models.MniCredencial:
    credencial = session.get(models.MniCredencial, credencial_id)
    if credencial is None or credencial.escritorio_id != escritorio_id:
        raise MniCredencialNotFound(str(credencial_id))
    credencial.ativo = False
    session.flush()
    _audit(session, acao="mni_credencial_desativada", credencial=credencial, ator="usuario")
    return credencial


def load_credencial_senha(session: Session, credencial: models.MniCredencial) -> str:
    return load_secret(session, credencial.referencia_vault)


def mark_validated(session: Session, credencial: models.MniCredencial) -> None:
    credencial.last_validated_at = datetime.now(timezone.utc)
    session.flush()
```

`backend/app/api/mni_routes.py` (seguir `autos_routes.py` para imports de
`get_session`/`get_current_user` — copiar exatamente o mesmo par de imports
que aquele módulo usa):

```python
"""Rotas de credencial MNI: cadastro, lista mascarada, teste e revogação."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, get_session  # conferir caminho real em autos_routes.py
from app.connectors.errors import ConnectorError
from app.connectors.mni import credentials as mni_credentials
from app.connectors.mni.client import MniClient
from app.connectors.mni.profiles import resolve_mni_profile
from app.sor import models

router = APIRouter(tags=["mni"])


class MniCredencialIn(BaseModel):
    tribunal: str
    id_consultante: str
    senha: str


class MniCredencialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tribunal: str
    id_consultante_mask: str
    ativo: bool
    last_validated_at: datetime | None


class MniTesteIn(BaseModel):
    numero_processo: str
    grau: str = "1"


class MniTesteOut(BaseModel):
    ok: bool
    error_code: str | None = None
    documentos: int | None = None


def _mask(value: str) -> str:
    return value[:3] + "***" if len(value) > 3 else "***"


def _out(credencial: models.MniCredencial) -> MniCredencialOut:
    return MniCredencialOut(
        id=credencial.id,
        tribunal=credencial.tribunal,
        id_consultante_mask=_mask(credencial.id_consultante),
        ativo=credencial.ativo,
        last_validated_at=credencial.last_validated_at,
    )


@router.post("/mni/credenciais", response_model=MniCredencialOut)
def cadastrar_mni(
    payload: MniCredencialIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> MniCredencialOut:
    credencial = mni_credentials.store_mni_credencial(
        session,
        escritorio_id=current.escritorio_id,
        usuario_id=current.usuario_id,
        tribunal=payload.tribunal,
        id_consultante=payload.id_consultante,
        senha=payload.senha,
    )
    session.commit()
    return _out(credencial)


@router.get("/mni/credenciais", response_model=list[MniCredencialOut])
def listar_mni(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> list[MniCredencialOut]:
    rows = session.scalars(
        select(models.MniCredencial)
        .where(models.MniCredencial.escritorio_id == current.escritorio_id)
        .order_by(models.MniCredencial.tribunal)
    )
    return [_out(row) for row in rows]


@router.delete("/mni/credenciais/{credencial_id}", response_model=MniCredencialOut)
def revogar_mni(
    credencial_id: int,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> MniCredencialOut:
    try:
        credencial = mni_credentials.deactivate_mni_credencial(
            session, credencial_id=credencial_id, escritorio_id=current.escritorio_id
        )
    except mni_credentials.MniCredencialNotFound:
        raise HTTPException(status_code=404, detail="credencial nao encontrada")
    session.commit()
    return _out(credencial)


@router.post("/mni/credenciais/{credencial_id}/testar", response_model=MniTesteOut)
def testar_mni(
    credencial_id: int,
    payload: MniTesteIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> MniTesteOut:
    credencial = session.get(models.MniCredencial, credencial_id)
    if credencial is None or credencial.escritorio_id != current.escritorio_id:
        raise HTTPException(status_code=404, detail="credencial nao encontrada")
    profile = resolve_mni_profile(credencial.tribunal, payload.grau)
    if profile is None:
        raise HTTPException(status_code=422, detail="mni_profile_missing")
    client = MniClient(
        url_endpoint=profile.url_endpoint,
        id_consultante=credencial.id_consultante,
        senha=mni_credentials.load_credencial_senha(session, credencial),
    )
    try:
        result = client.consultar_processo(payload.numero_processo)
    except ConnectorError as exc:
        session.commit()
        return MniTesteOut(ok=False, error_code=exc.code)
    mni_credentials.mark_validated(session, credencial)
    session.commit()
    return MniTesteOut(ok=True, documentos=len(result.documentos))
```

Em `backend/app/api/main.py`, junto da inclusão dos routers existentes
(procurar `include_router`):

```python
from app.api.mni_routes import router as mni_router
app.include_router(mni_router)
```

- [ ] **Step 4: Run service + route tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mni_credentials.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/vault/service.py backend/app/connectors/mni/credentials.py backend/app/api/mni_routes.py backend/app/api/main.py backend/tests/test_mni_credentials.py
git commit -m "feat(mni): vault-backed credentials with masked API and test endpoint"
```

---

### Task 6: Roteamento em `open_capture` + executor + worker drain

**Files:**

- Modify: `backend/app/autos/service.py`
- Create: `backend/app/connectors/mni/executor.py`
- Modify: `backend/app/autos/worker.py`
- Modify: `backend/app/cli.py`
- Modify: `backend/app/api/autos_routes.py`
- Create: `backend/tests/test_mni_capture_flow.py`

**Interfaces:**

- Consumes: `find_active_credencial`, `resolve_mni_profile`, `MniReaderDriver`, `MniClient`, `load_credencial_senha` (Tasks 1–5); `record_initial_manifest`/`confirm_document_upload`/`finalize_capture` (existentes).
- Produces: `autos_service.resolve_capture_fonte(session, instancia) -> str`; `open_capture(..., fonte=None)` cria job `mni_capture` quando `fonte=="mni"`; `executor.run_mni_capture_job(session, *, capture_id, object_store=None, driver=None) -> CapturaAutos`; `worker.process_due_mni_captures(session_factory) -> int`.

- [ ] **Step 1: Write failing flow tests**

```python
# backend/tests/test_mni_capture_flow.py
"""Roteamento e executor MNI: fonte certa, pipeline de integridade intacto."""

import pytest
from sqlalchemy import select

from app.autos import service as autos_service
from app.connectors.mni import credentials as mni_credentials
from app.connectors.mni.executor import run_mni_capture_job
from app.sor import models
from app.storage.objects import get_object_store


@pytest.fixture()
def instancia_tjmg(db_session, seeded):
    processo = models.Processo(
        escritorio_id=seeded.escritorio_id,
        numero="0000000-00.2026.8.13.0000",
        tribunal="TJMG",
        sistema="PJe",
    )
    db_session.add(processo)
    db_session.flush()
    instancia = models.ProcessoInstancia(
        processo_id=processo.id,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        status="active",
    )
    db_session.add(instancia)
    db_session.flush()
    return instancia


def test_open_capture_sem_credencial_usa_agente(db_session, seeded, instancia_tjmg):
    capture = autos_service.open_capture(
        db_session, processo_instancia=instancia_tjmg, usuario_id=seeded.usuario_id
    )
    assert capture.fonte == "agente"
    assert capture.agent_command_id is not None


def test_open_capture_com_credencial_enfileira_job_mni(db_session, seeded, instancia_tjmg):
    mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id, usuario_id=seeded.usuario_id,
        tribunal="TJMG", id_consultante="123", senha="s",
    )
    capture = autos_service.open_capture(
        db_session, processo_instancia=instancia_tjmg, usuario_id=seeded.usuario_id
    )
    assert capture.fonte == "mni"
    assert capture.agent_command_id is None
    job = db_session.scalars(
        select(models.JobExecucao).where(models.JobExecucao.tipo == "mni_capture")
    ).one()
    assert job.payload["capture_id"] == capture.id


class FakeDriver:
    """Driver fake com dois documentos válidos; sem rede."""

    sistema = "MNI"

    def __init__(self):
        from datetime import datetime, timezone

        from app.connectors.contracts import CourtDocumentRef, CourtManifestSnapshot

        self._refs = (
            CourtDocumentRef(
                external_id="SIM-DOC-001", nome="Peticao.pdf", tipo="1", ordem=1,
                data_documento=None, sigiloso=False, mime_type="application/pdf",
                size_hint=None, download_ref="SIM-DOC-001",
            ),
            CourtDocumentRef(
                external_id="SIM-DOC-002", nome="Decisao.pdf", tipo="4", ordem=2,
                data_documento=None, sigiloso=False, mime_type="application/pdf",
                size_hint=None, download_ref="SIM-DOC-002",
            ),
        )
        self._snapshot_factory = lambda target: CourtManifestSnapshot(
            target=target, documentos=self._refs, cursor_complete=True,
            source_fingerprint="sha256:fixo", captured_at=datetime.now(timezone.utc),
            evidence={"fonte": "mni", "documentos": 2, "conteudo_inline": False},
        )

    def enumerate_documents(self, target):
        return self._snapshot_factory(target)

    def prefetch(self, target, refs):
        return None

    def download_document(self, target, ref):
        return b"%PDF-1.4\n%" + ref.external_id.encode() + b"\n%%EOF\n"


def test_executor_completa_captura_com_prova_de_integridade(
    db_session, seeded, instancia_tjmg
):
    mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id, usuario_id=seeded.usuario_id,
        tribunal="TJMG", id_consultante="123", senha="s",
    )
    capture = autos_service.open_capture(
        db_session, processo_instancia=instancia_tjmg, usuario_id=seeded.usuario_id
    )
    result = run_mni_capture_job(
        db_session, capture_id=capture.id, object_store=get_object_store(),
        driver=FakeDriver(),
    )
    assert result.status == "complete"
    assert result.captured_count == 2
    versions = db_session.scalars(select(models.DocumentoArquivo)).all()
    assert len(versions) == 2
    assert all(v.sha256 for v in versions)


def test_executor_marca_failed_em_erro_canonico(db_session, seeded, instancia_tjmg):
    from app.connectors.errors import MniUnavailable

    class BrokenDriver(FakeDriver):
        def enumerate_documents(self, target):
            raise MniUnavailable("endpoint fora")

    mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id, usuario_id=seeded.usuario_id,
        tribunal="TJMG", id_consultante="123", senha="s",
    )
    capture = autos_service.open_capture(
        db_session, processo_instancia=instancia_tjmg, usuario_id=seeded.usuario_id
    )
    with pytest.raises(MniUnavailable):
        run_mni_capture_job(
            db_session, capture_id=capture.id, object_store=get_object_store(),
            driver=BrokenDriver(),
        )
    db_session.refresh(capture)
    assert capture.status == "failed"
    assert capture.error_code == "mni_unavailable"
```

Nota: conferir os campos obrigatórios reais de `models.Processo` no conftest
(`seeded`) e ajustar a fixture `instancia_tjmg` para o mínimo que o modelo
exige (ex.: `cliente_id` se for `nullable=False`).

- [ ] **Step 2: Run and verify failures**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mni_capture_flow.py -v`

Expected: FAIL — `resolve_capture_fonte`/executor inexistentes.

- [ ] **Step 3: Implement routing, executor and worker drain**

Em `backend/app/autos/service.py` — assinatura nova e branch (substituindo o
trecho do `enqueue_command` dentro de `open_capture`):

```python
def resolve_capture_fonte(session: Session, instancia: models.ProcessoInstancia) -> str:
    """MNI quando ha credencial ativa + perfil para a rota; senao agente."""
    from app.connectors.mni.credentials import find_active_credencial
    from app.connectors.mni.profiles import resolve_mni_profile

    if resolve_mni_profile(instancia.tribunal, instancia.grau) is None:
        return "agente"
    credencial = find_active_credencial(
        session, escritorio_id=instancia.escritorio_id, tribunal=instancia.tribunal
    )
    return "mni" if credencial is not None else "agente"


def open_capture(
    session: Session,
    *,
    processo_instancia: models.ProcessoInstancia,
    usuario_id: int | None,
    fonte: str | None = None,
) -> models.CapturaAutos:
    """Abre uma nova geração de captura e publica o trabalho na fonte certa."""
    processo = session.get(models.Processo, processo_instancia.processo_id)
    resolved = fonte or resolve_capture_fonte(session, processo_instancia)
    latest = session.scalar(
        select(func.max(models.CapturaAutos.generation)).where(
            models.CapturaAutos.processo_instancia_id == processo_instancia.id
        )
    )
    capture = models.CapturaAutos(
        escritorio_id=processo_instancia.escritorio_id,
        processo_instancia_id=processo_instancia.id,
        generation=(latest or 0) + 1,
        status="queued",
        started_at=_now(),
        fonte=resolved,
    )
    session.add(capture)
    session.flush()

    if resolved == "mni":
        from app.queue.jobs import create_job

        create_job(
            session,
            tipo="mni_capture",
            entidade="captura_autos",
            entidade_id=capture.id,
            payload={"capture_id": capture.id, "escritorio_id": capture.escritorio_id},
            ator=f"usuario:{usuario_id}" if usuario_id else "system",
        )
    else:
        command = enqueue_command(
            session,
            escritorio_id=processo_instancia.escritorio_id,
            usuario_id=usuario_id,
            tipo="read_process",
            idempotency_key=f"capture:{processo_instancia.id}:manifest:{capture.generation}",
            payload={
                "capture_id": capture.id,
                "processo_instancia_id": processo_instancia.id,
                "sistema": processo_instancia.sistema,
                "tribunal": processo_instancia.tribunal,
                "grau": processo_instancia.grau,
                "numero_processo": processo.numero if processo else None,
                "url_base": processo_instancia.url_base,
            },
        )
        capture.agent_command_id = command.id
    session.flush()
    return capture
```

`backend/app/connectors/mni/executor.py`:

```python
"""Executor in-backend da captura MNI.

Dirige as mesmas funções de integridade do Plano 2 usando o driver MNI;
nenhuma etapa relaxa a prova de completude. Erro canônico marca a captura
``failed`` e sobe — o job nunca fica ``running``.
"""

from __future__ import annotations

from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.autos import service as autos_service
from app.autos.contracts import ManifestDocumentInput, ManifestInput
from app.connectors.contracts import CourtManifestSnapshot, CourtTarget
from app.connectors.errors import ConnectorError, DocumentDownloadFailed
from app.connectors.mni.client import MniClient
from app.connectors.mni.credentials import find_active_credencial, load_credencial_senha
from app.connectors.mni.profiles import resolve_mni_profile
from app.connectors.mni.reader import MniReaderDriver
from app.sor import models
from app.storage.objects import ObjectStore, get_object_store

_ACTIVE_STATUSES = {"queued", "enumerating", "downloading", "verifying"}


class MniCaptureError(RuntimeError):
    def __init__(self, code: str, detail: str | None = None):
        super().__init__(detail or code)
        self.code = code


def _target_for(session: Session, capture: models.CapturaAutos) -> CourtTarget:
    instancia = session.get(models.ProcessoInstancia, capture.processo_instancia_id)
    processo = session.get(models.Processo, instancia.processo_id)
    return CourtTarget(
        processo_instancia_id=instancia.id,
        processo_id=processo.id,
        numero_processo=processo.numero,
        sistema=instancia.sistema,
        tribunal=instancia.tribunal,
        grau=instancia.grau,
        url_base=instancia.url_base or "",
    )


def _manifest_input(snapshot: CourtManifestSnapshot) -> ManifestInput:
    return ManifestInput(
        cursor_complete=snapshot.cursor_complete,
        documents=[
            ManifestDocumentInput(
                external_id=ref.external_id,
                nome=ref.nome,
                tipo=ref.tipo,
                ordem=ref.ordem,
                parent_external_id=ref.parent_external_id,
                data_documento=ref.data_documento,
                sigiloso=ref.sigiloso,
                mime_type=ref.mime_type,
                size_hint=ref.size_hint,
                download_ref=ref.download_ref,
            )
            for ref in snapshot.documentos
        ],
        evidence=snapshot.evidence,
    )


def build_driver(session: Session, capture: models.CapturaAutos) -> MniReaderDriver:
    instancia = session.get(models.ProcessoInstancia, capture.processo_instancia_id)
    profile = resolve_mni_profile(instancia.tribunal, instancia.grau)
    credencial = find_active_credencial(
        session, escritorio_id=capture.escritorio_id, tribunal=instancia.tribunal
    )
    if profile is None or credencial is None:
        raise MniCaptureError("mni_route_unavailable")
    client = MniClient(
        url_endpoint=profile.url_endpoint,
        id_consultante=credencial.id_consultante,
        senha=load_credencial_senha(session, credencial),
    )
    return MniReaderDriver(client)


def run_mni_capture_job(
    session: Session,
    *,
    capture_id: int,
    object_store: ObjectStore | None = None,
    driver: MniReaderDriver | None = None,
) -> models.CapturaAutos:
    capture = session.get(models.CapturaAutos, capture_id)
    if capture is None:
        raise MniCaptureError("capture_not_found", str(capture_id))
    if capture.fonte != "mni":
        raise MniCaptureError("wrong_source", capture.fonte)

    store = object_store or get_object_store()
    drv = driver or build_driver(session, capture)
    target = _target_for(session, capture)
    try:
        snapshot = drv.enumerate_documents(target)
        autos_service.record_initial_manifest(
            session, capture=capture, manifest=_manifest_input(snapshot)
        )
        items = {
            item.external_id: item
            for item in session.scalars(
                select(models.ManifestoItem).where(
                    models.ManifestoItem.captura_id == capture.id
                )
            )
        }
        drv.prefetch(target, snapshot.documentos)
        for ref in snapshot.documentos:
            item = items[ref.external_id]
            try:
                data = drv.download_document(target, ref)
            except DocumentDownloadFailed as exc:
                item.status = "failed"
                item.error_code = exc.code
                session.flush()
                continue
            digest = sha256(data).hexdigest()
            key = (
                f"tenant/{capture.escritorio_id}/process/{target.processo_id}"
                f"/instance/{target.processo_instancia_id}"
                f"/document/{item.documento_id}/{digest}.bin"
            )
            store.put_bytes(key, data, ref.mime_type or "application/pdf")
            try:
                autos_service.confirm_document_upload(
                    session,
                    capture=capture,
                    external_id=ref.external_id,
                    object_key=key,
                    reported_sha256=digest,
                    object_store=store,
                    mime_type=ref.mime_type or "application/pdf",
                )
            except autos_service.CaptureError:
                # item ja marcado failed (hash_mismatch/invalid_pdf); segue
                continue
        final = drv.enumerate_documents(target)
        return autos_service.finalize_capture(
            session, capture=capture, final_manifest=_manifest_input(final)
        )
    except ConnectorError as exc:
        if capture.status in _ACTIVE_STATUSES:
            capture.status = "failed"
            capture.error_code = exc.code
            session.flush()
        raise
```

Em `backend/app/autos/worker.py`, no fim do arquivo (espelha
`process_due_purges`):

```python
def claim_due_mni_captures(session: Session, *, limit: int = 10) -> list[models.JobExecucao]:
    stmt = (
        select(models.JobExecucao)
        .where(
            models.JobExecucao.tipo == "mni_capture",
            models.JobExecucao.status == "queued",
        )
        .order_by(models.JobExecucao.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    jobs = list(session.scalars(stmt))
    for job in jobs:
        job.status = "running"
    session.flush()
    return jobs


def process_due_mni_captures(session_factory) -> int:
    """Drena jobs `mni_capture`. Retorna a contagem processada."""
    from app.connectors.mni.executor import MniCaptureError, run_mni_capture_job

    processed = 0
    while True:
        with session_factory() as session:
            jobs = claim_due_mni_captures(session, limit=1)
            if not jobs:
                return processed
            job = jobs[0]
            capture_id = (job.payload or {}).get("capture_id")
            try:
                capture = run_mni_capture_job(session, capture_id=capture_id)
                job.status = "completed"
                job.resultado = {"capture_id": capture_id, "status": capture.status}
            except (MniCaptureError, Exception) as exc:  # noqa: BLE001 - vira estado observável
                job.status = "failed"
                job.erro = getattr(exc, "code", str(exc))[:500]
            session.commit()
        processed += 1
```

Em `backend/app/cli.py`, no bloco `process-autos-due` (linha ~207), adicionar
a drenagem MNI ao lado das existentes:

```python
        mni = process_due_mni_captures(session_factory)
        print(
            f"process-autos-due: {processed} extração(ões), {purged} purge(s), "
            f"{mni} captura(s) MNI."
        )
```

(importando `process_due_mni_captures` junto dos imports do worker já usados
nesse comando).

Em `backend/app/api/autos_routes.py`, no schema `CapturaOut`, adicionar:

```python
    fonte: str = "agente"
```

- [ ] **Step 4: Run flow tests + full autos regressions**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mni_capture_flow.py -q
.\.venv\Scripts\python.exe -m pytest tests -k "autos or capture" -q
```

Expected: PASS em ambos; nenhum teste existente de captura por agente quebra.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/autos/service.py backend/app/connectors/mni/executor.py backend/app/autos/worker.py backend/app/cli.py backend/app/api/autos_routes.py backend/tests/test_mni_capture_flow.py
git commit -m "feat(mni): route captures to in-backend executor with integrity pipeline"
```

---

### Task 7: Simulador SOAP MNI + integração ponta a ponta

**Files:**

- Create: `backend/app/connectors/simulators/mni.py`
- Create: `backend/tests/test_mni_simulator_integration.py`

**Interfaces:**

- Produces: `MniSimulator(senha_valida="sim-senha")` + `build_mni_server(simulator, host, port=0) -> ThreadingHTTPServer` servindo `consultarProcesso` sintético (POST).

- [ ] **Step 1: Write the integration test first**

```python
# backend/tests/test_mni_simulator_integration.py
"""Ponta a ponta real: cliente HTTP → simulador SOAP → executor → complete."""

import threading

import pytest

from app.autos import service as autos_service
from app.connectors.errors import AccessDenied
from app.connectors.mni import credentials as mni_credentials
from app.connectors.mni.client import MniClient
from app.connectors.mni.executor import run_mni_capture_job
from app.connectors.mni.reader import MniReaderDriver
from app.connectors.simulators.mni import MniSimulator, build_mni_server
from app.sor import models
from app.storage.objects import get_object_store


@pytest.fixture()
def mni_server():
    simulator = MniSimulator()
    server = build_mni_server(simulator, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/intercomunicacao"
    server.shutdown()


@pytest.fixture()
def instancia_tjmg(db_session, seeded):
    processo = models.Processo(
        escritorio_id=seeded.escritorio_id,
        numero="0000000-00.2026.8.13.0000",
        tribunal="TJMG",
        sistema="PJe",
    )
    db_session.add(processo)
    db_session.flush()
    instancia = models.ProcessoInstancia(
        processo_id=processo.id, escritorio_id=seeded.escritorio_id,
        sistema="PJe", tribunal="TJMG", grau="1", status="active",
    )
    db_session.add(instancia)
    db_session.flush()
    return instancia


def test_captura_completa_contra_simulador(db_session, seeded, instancia_tjmg, mni_server):
    mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id, usuario_id=seeded.usuario_id,
        tribunal="TJMG", id_consultante="12345678900", senha="sim-senha",
    )
    capture = autos_service.open_capture(
        db_session, processo_instancia=instancia_tjmg, usuario_id=seeded.usuario_id
    )
    client = MniClient(
        url_endpoint=mni_server, id_consultante="12345678900", senha="sim-senha"
    )
    result = run_mni_capture_job(
        db_session, capture_id=capture.id, object_store=get_object_store(),
        driver=MniReaderDriver(client),
    )
    assert result.status == "complete"
    assert result.expected_count == 3
    assert result.captured_count == 3


def test_senha_errada_vira_access_denied(mni_server):
    client = MniClient(
        url_endpoint=mni_server, id_consultante="12345678900", senha="errada"
    )
    with pytest.raises(AccessDenied):
        client.consultar_processo("0000000-00.2026.8.13.0000")
```

- [ ] **Step 2: Run and verify missing simulator**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mni_simulator_integration.py -v`

Expected: FAIL on import.

- [ ] **Step 3: Implement the SOAP simulator**

```python
# backend/app/connectors/simulators/mni.py
"""Simulador SOAP do MNI, sanitizado como os demais simuladores.

Serve ``consultarProcesso`` com os documentos SIM-DOC-001..003 (um vinculado
e sigiloso); senha errada devolve ``sucesso=false`` com mensagem de
autorização. Nada aqui contém dado real.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.connectors.simulators.base import SimulatorDocument, _default_documents


def _doc_xml(doc: SimulatorDocument, *, include_content: bool, requested: set[str]) -> str:
    conteudo = ""
    if include_content and (not requested or doc.external_id in requested):
        payload = base64.b64encode(doc.pdf_bytes).decode("ascii")
        conteudo = f"<conteudo>{payload}</conteudo>"
    attrs = (
        f'idDocumento="{doc.external_id}" tipoDocumento="1" '
        f'dataHora="20260701120000" mimetype="application/pdf" '
        f'nivelSigilo="{1 if doc.sigiloso else 0}" descricao="{doc.nome}"'
    )
    return f"<documento {attrs}>{conteudo}</documento>"


@dataclass
class MniSimulator:
    senha_valida: str = "sim-senha"
    documents: list[SimulatorDocument] = field(default_factory=_default_documents)

    def responder(self, body: str) -> str:
        senha_ok = f"<ser:senhaConsultante>{self.senha_valida}</ser:senhaConsultante>" in body
        if not senha_ok:
            return self._envelope(
                "<sucesso>false</sucesso><mensagem>Usuario ou senha invalidos</mensagem>"
            )
        requested = {
            doc.external_id
            for doc in self.documents
            if f">{doc.external_id}</ser:documento>" in body
        }
        include_content = bool(requested)
        docs = "".join(
            _doc_xml(doc, include_content=include_content, requested=requested)
            for doc in self.documents
        )
        return self._envelope(
            "<sucesso>true</sucesso><mensagem>ok</mensagem>"
            f"<processo><dadosBasicos numero='00000000020268130000' nivelSigilo='0'/>{docs}</processo>"
        )

    @staticmethod
    def _envelope(inner: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:ns2="http://www.cnj.jus.br/intercomunicacao-2.2.2">'
            f"<soap:Body><ns2:consultarProcessoResposta>{inner}"
            "</ns2:consultarProcessoResposta></soap:Body></soap:Envelope>"
        )


def build_mni_server(
    simulator: MniSimulator, host: str = "127.0.0.1", port: int = 0
) -> ThreadingHTTPServer:
    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib API
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            response = simulator.responder(body).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/xml; charset=utf-8")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib API
            return

    return ThreadingHTTPServer((host, port), _Handler)
```

Atenção a um detalhe do simulador vs. driver: a enumeração (sem ids) devolve
os 3 documentos **sem** `documentoVinculado` aninhado — os 3 saem como
`documento` planos; o driver então enxerga `SIM-DOC-003` sem `parent_id`. Isso
é aceitável para o teste de integração (a relação pai/filho já é coberta no
unit do client); o fingerprint continua estável entre as duas enumerações.

- [ ] **Step 4: Run integration tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mni_simulator_integration.py -q`

Expected: PASS — captura `complete` com 3/3 e senha errada mapeando
`AccessDenied`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/connectors/simulators/mni.py backend/tests/test_mni_simulator_integration.py
git commit -m "test(mni): sanitized SOAP simulator with end-to-end capture"
```

---

### Task 8: Frontend — credenciais MNI em Configurações + fonte da captura

**Files:**

- Modify: `frontend/lib/api.ts`
- Create: `frontend/app/components/MniSection.tsx`
- Create: `frontend/app/components/MniSection.test.tsx`
- Modify: `frontend/app/SettingsModal.tsx`

**Interfaces:**

- Produces em `lib/api.ts`: `MniCredencial { id, tribunal, id_consultante_mask, ativo, last_validated_at }`; `MniTesteResultado { ok, error_code, documentos }`; `listarMniCredenciais()`, `cadastrarMniCredencial(payload)`, `revogarMniCredencial(id)`, `testarMniCredencial(id, numeroProcesso)`; campo `fonte?: string` no tipo de captura de `AutosStatus`.

- [ ] **Step 1: Write failing component test**

```tsx
// frontend/app/components/MniSection.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MniSection } from "./MniSection";

const api = vi.hoisted(() => ({
  listarMniCredenciais: vi.fn(),
  cadastrarMniCredencial: vi.fn(),
  revogarMniCredencial: vi.fn(),
  testarMniCredencial: vi.fn(),
}));

vi.mock("@/lib/api", () => api);

describe("MniSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listarMniCredenciais.mockResolvedValue([
      {
        id: 1,
        tribunal: "TJMG",
        id_consultante_mask: "123***",
        ativo: true,
        last_validated_at: null,
      },
    ]);
  });

  it("lista credenciais mascaradas", async () => {
    render(<MniSection />);
    expect(await screen.findByText("TJMG")).toBeInTheDocument();
    expect(screen.getByText("123***")).toBeInTheDocument();
    expect(screen.queryByText(/senha/i)).not.toBeNull(); // campo do form existe
  });

  it("cadastra credencial nova e recarrega a lista", async () => {
    api.cadastrarMniCredencial.mockResolvedValue({
      id: 2, tribunal: "TJBA", id_consultante_mask: "987***",
      ativo: true, last_validated_at: null,
    });
    render(<MniSection />);
    await screen.findByText("TJMG");
    fireEvent.change(screen.getByLabelText(/tribunal/i), { target: { value: "TJBA" } });
    fireEvent.change(screen.getByLabelText(/consultante/i), { target: { value: "98765432100" } });
    fireEvent.change(screen.getByLabelText(/senha/i), { target: { value: "s" } });
    fireEvent.click(screen.getByRole("button", { name: /cadastrar/i }));
    await waitFor(() =>
      expect(api.cadastrarMniCredencial).toHaveBeenCalledWith({
        tribunal: "TJBA", id_consultante: "98765432100", senha: "s",
      })
    );
  });

  it("revoga credencial", async () => {
    api.revogarMniCredencial.mockResolvedValue(undefined);
    render(<MniSection />);
    await screen.findByText("TJMG");
    fireEvent.click(screen.getByRole("button", { name: /revogar/i }));
    await waitFor(() => expect(api.revogarMniCredencial).toHaveBeenCalledWith(1));
  });
});
```

Conferir o alias de import usado nos testes vizinhos (`@/lib/api` vs
`../../lib/api`) — usar o mesmo padrão de `AgentSection.test.tsx` (ou
componente de teste vizinho equivalente) para mock e render.

- [ ] **Step 2: Run and verify failure**

Run (em `frontend/`): `pnpm test -- MniSection`

Expected: FAIL — componente inexistente.

- [ ] **Step 3: Implement API calls and component**

Em `frontend/lib/api.ts`, junto dos tipos e das funções de credenciais
existentes (`listarCredenciais`, ~linha 518), seguindo o mesmo helper HTTP
que as funções vizinhas usam:

```ts
export interface MniCredencial {
  id: number;
  tribunal: string;
  id_consultante_mask: string;
  ativo: boolean;
  last_validated_at: string | null;
}

export interface MniTesteResultado {
  ok: boolean;
  error_code: string | null;
  documentos: number | null;
}

export async function listarMniCredenciais(): Promise<MniCredencial[]> {
  return apiGet("/mni/credenciais");
}

export async function cadastrarMniCredencial(payload: {
  tribunal: string;
  id_consultante: string;
  senha: string;
}): Promise<MniCredencial> {
  return apiPost("/mni/credenciais", payload);
}

export async function revogarMniCredencial(credencialId: number): Promise<void> {
  await apiDelete(`/mni/credenciais/${credencialId}`);
}

export async function testarMniCredencial(
  credencialId: number,
  numeroProcesso: string,
): Promise<MniTesteResultado> {
  return apiPost(`/mni/credenciais/${credencialId}/testar`, {
    numero_processo: numeroProcesso,
  });
}
```

(`apiGet`/`apiPost`/`apiDelete` são ilustrativos: usar exatamente o helper
de fetch autenticado que `listarCredenciais`/`cadastrarCredencial` usam no
arquivo.) No tipo de captura dentro de `AutosStatus`, adicionar
`fonte?: string;`.

`frontend/app/components/MniSection.tsx`:

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";

import {
  cadastrarMniCredencial,
  listarMniCredenciais,
  MniCredencial,
  revogarMniCredencial,
  testarMniCredencial,
} from "@/lib/api";

export function MniSection() {
  const [credenciais, setCredenciais] = useState<MniCredencial[]>([]);
  const [tribunal, setTribunal] = useState("");
  const [idConsultante, setIdConsultante] = useState("");
  const [senha, setSenha] = useState("");
  const [numeroTeste, setNumeroTeste] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const recarregar = useCallback(async () => {
    try {
      setCredenciais(await listarMniCredenciais());
    } catch {
      setFeedback("Falha ao carregar credenciais MNI.");
    }
  }, []);

  useEffect(() => {
    void recarregar();
  }, [recarregar]);

  async function onCadastrar() {
    setBusy(true);
    setFeedback(null);
    try {
      await cadastrarMniCredencial({
        tribunal: tribunal.trim().toUpperCase(),
        id_consultante: idConsultante.trim(),
        senha,
      });
      setTribunal("");
      setIdConsultante("");
      setSenha("");
      await recarregar();
      setFeedback("Credencial MNI cadastrada.");
    } catch {
      setFeedback("Falha ao cadastrar credencial MNI.");
    } finally {
      setBusy(false);
    }
  }

  async function onRevogar(id: number) {
    setBusy(true);
    try {
      await revogarMniCredencial(id);
      await recarregar();
    } finally {
      setBusy(false);
    }
  }

  async function onTestar(id: number) {
    if (!numeroTeste.trim()) {
      setFeedback("Informe um numero de processo para o teste.");
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      const result = await testarMniCredencial(id, numeroTeste.trim());
      setFeedback(
        result.ok
          ? `Conexao MNI ok (${result.documentos ?? 0} documento(s) listados).`
          : `Teste falhou: ${result.error_code}`,
      );
      await recarregar();
    } catch {
      setFeedback("Falha ao testar credencial MNI.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Consulta oficial (MNI)">
      <h3>Consulta oficial (MNI)</h3>
      <p>
        Credencial de consulta obtida no credenciamento junto ao tribunal. Com
        ela ativa, a captura dos autos usa o webservice oficial em vez do
        agente local.
      </p>
      {credenciais.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Tribunal</th>
              <th>Consultante</th>
              <th>Status</th>
              <th>Ultima validacao</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {credenciais.map((cred) => (
              <tr key={cred.id}>
                <td>{cred.tribunal}</td>
                <td>{cred.id_consultante_mask}</td>
                <td>{cred.ativo ? "Ativa" : "Revogada"}</td>
                <td>{cred.last_validated_at ?? "nunca"}</td>
                <td>
                  {cred.ativo && (
                    <>
                      <button type="button" disabled={busy} onClick={() => onTestar(cred.id)}>
                        Testar
                      </button>
                      <button type="button" disabled={busy} onClick={() => onRevogar(cred.id)}>
                        Revogar
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div>
        <label>
          Tribunal
          <input value={tribunal} onChange={(e) => setTribunal(e.target.value)} placeholder="TJMG" />
        </label>
        <label>
          Id consultante
          <input
            value={idConsultante}
            onChange={(e) => setIdConsultante(e.target.value)}
            placeholder="CPF/CNPJ do credenciamento"
          />
        </label>
        <label>
          Senha
          <input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} />
        </label>
        <button type="button" disabled={busy || !tribunal || !idConsultante || !senha} onClick={onCadastrar}>
          Cadastrar
        </button>
      </div>
      <label>
        Processo para teste
        <input
          value={numeroTeste}
          onChange={(e) => setNumeroTeste(e.target.value)}
          placeholder="numero CNJ para validar a conexao"
        />
      </label>
      {feedback && <p role="status">{feedback}</p>}
    </section>
  );
}
```

Ajustar classes/markup ao padrão visual dos componentes vizinhos da seção
"Acesso aos tribunais" (`AgentSection.tsx`) na hora de integrar. Em
`frontend/app/SettingsModal.tsx`, importar e renderizar `<MniSection />`
imediatamente após o componente do agente na seção "Acesso aos tribunais".

- [ ] **Step 4: Run frontend verification**

```powershell
cd frontend
pnpm test
pnpm typecheck
pnpm build
```

Expected: todos com exit `0`.

- [ ] **Step 5: Commit**

```powershell
git add frontend/lib/api.ts frontend/app/components/MniSection.tsx frontend/app/components/MniSection.test.tsx frontend/app/SettingsModal.tsx
git commit -m "feat(frontend): MNI credentials in unified court-access settings"
```

---

### Task 9: Teste live opt-in + documentação de estado

**Files:**

- Create: `backend/tests/live/test_mni_live.py`
- Modify: `docs/estado.md`

**Interfaces:**

- Live test lê `CAUSOR_MNI_LIVE_COURT`, `CAUSOR_MNI_LIVE_DEGREE`, `CAUSOR_MNI_LIVE_PROCESS`, `CAUSOR_MNI_LIVE_ID`, `CAUSOR_MNI_LIVE_SENHA` do ambiente; roda só com `RUN_MNI_LIVE=1`.

- [ ] **Step 1: Write skip-safe live test**

```python
# backend/tests/live/test_mni_live.py
"""Validação live do MNI — só na máquina autorizada, nunca em CI.

Requer credenciamento aprovado no tribunal alvo e um processo do próprio
advogado seguro para leitura. Duas enumerações devem ter fingerprint
idêntico antes de qualquer promoção de perfil (verificado=True).
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_MNI_LIVE") != "1",
    reason="set RUN_MNI_LIVE=1 on the authorized machine",
)


def _client():
    from app.connectors.mni.client import MniClient
    from app.connectors.mni.profiles import resolve_mni_profile

    profile = resolve_mni_profile(
        os.environ["CAUSOR_MNI_LIVE_COURT"], os.environ["CAUSOR_MNI_LIVE_DEGREE"]
    )
    assert profile is not None, "registre o perfil do tribunal antes do teste live"
    return MniClient(
        url_endpoint=profile.url_endpoint,
        id_consultante=os.environ["CAUSOR_MNI_LIVE_ID"],
        senha=os.environ["CAUSOR_MNI_LIVE_SENHA"],
    )


def test_live_consulta_lista_documentos_com_fingerprint_estavel():
    from app.connectors.contracts import CourtTarget
    from app.connectors.mni.reader import MniReaderDriver

    driver = MniReaderDriver(_client())
    target = CourtTarget(
        processo_instancia_id=0, processo_id=0,
        numero_processo=os.environ["CAUSOR_MNI_LIVE_PROCESS"],
        sistema="PJe", tribunal=os.environ["CAUSOR_MNI_LIVE_COURT"],
        grau=os.environ["CAUSOR_MNI_LIVE_DEGREE"], url_base="",
    )
    first = driver.enumerate_documents(target)
    second = driver.enumerate_documents(target)
    assert first.cursor_complete is True
    assert first.documentos, "processo live sem documentos listados"
    assert first.source_fingerprint == second.source_fingerprint
```

- [ ] **Step 2: Run default suite and verify skip**

Run: `.\.venv\Scripts\python.exe -m pytest tests/live/test_mni_live.py -v`

Expected: SKIPPED, exit `0`.

- [ ] **Step 3: Update estado.md**

Adicionar ao bloco de status corrente de `docs/estado.md` (após o item do
Plano 2/Marco A):

```markdown
- **2026-07-21 — Leitura oficial dos autos via MNI implementada** (spec
  `docs/superpowers/specs/2026-07-21-mni-leitura-autos-design.md`): cliente
  SOAP no backend, credencial por tribunal no vault, captura roteada por
  `CapturaAutos.fonte` ("mni" | "agente") pelo mesmo pipeline de integridade
  do Plano 2, UI de credenciais em Configuracoes → Acesso aos tribunais.
  Validacao live e a promocao dos perfis (`verificado=True`) dependem do
  credenciamento MNI junto ao primeiro tribunal (oficio a DTI) — processo
  administrativo, sem custo.
```

E no "Ainda falta para MVP real", acrescentar:

```markdown
8. Solicitar o credenciamento MNI no tribunal do piloto e rodar
   `RUN_MNI_LIVE=1` para promover o primeiro perfil.
```

- [ ] **Step 4: Full verification**

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
cd ..\frontend
pnpm test
pnpm typecheck
pnpm build
```

Expected: tudo verde; live tests skipped.

- [ ] **Step 5: Commit**

```powershell
git add backend/tests/live/test_mni_live.py docs/estado.md
git commit -m "test(mni): opt-in live validation and status docs"
```

---

## Acceptance gate

- [ ] Cliente MNI parseia lista, teor, auth-fail e fault com erros canônicos; senha nunca em repr/erro/log.
- [ ] Perfis fail-closed por `(tribunal, grau)`; sem perfil ⇒ captura cai no agente.
- [ ] `open_capture` roteia por credencial ativa + perfil; regressão do caminho agente verde.
- [ ] Executor completa captura com prova de integridade (duas enumerações, hash recomputado, PDF validado) e nunca deixa job/captura `running` em erro.
- [ ] API de credenciais isolada por tenant, senha só no vault, lista mascarada.
- [ ] UI cadastra/testa/revoga credencial; `fonte` visível no status dos autos.
- [ ] Integração ponta a ponta contra simulador SOAP: `complete` 3/3.
- [ ] Suíte completa backend+frontend verde; live MNI skipped por default.
