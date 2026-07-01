# Integração back ↔ front + chat agêntico — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar os gaps de integração back↔front (captura OAB real, auditoria, revisão de prazo, surfacing da classificação de IA) e adicionar um assistente conversacional **agêntico** que lê o SOR e propõe ações do fluxo, sempre preservando o gate humano.

**Architecture:** O backend roda um loop de tool-use do Claude em `POST /chat`: ferramentas de **leitura** executam contra o SOR; ferramentas de **ação** são interceptadas e devolvidas como *propostas* que o front renderiza como cards de confirmação (a execução real usa os endpoints REST existentes, auditada como `usuario:N`). `protocolar` nunca é exposto como ferramenta. Conversas são stateless (o front guarda o histórico).

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy / `anthropic` SDK (manual agentic loop) / pytest. Frontend Next.js + TypeScript.

**Convenções de comando (rodar de `/backend`):**
- Testes: `./.venv/Scripts/python.exe -m pytest -q`
- Um teste: `./.venv/Scripts/python.exe -m pytest tests/test_api.py::NOME -v`
- Lint: `./.venv/Scripts/python.exe -m ruff check .`
- Frontend type-check (de `/frontend`): `npx tsc --noEmit`

**Nota de modelo:** o assistente usa modelo Claude configurável; o padrão atual usa Haiku para chat/classificação e Sonnet para minuta.

---

### Task 1: Schemas de chat — ProposedAction + ChatResponse estendido

**Files:**
- Modify: `backend/app/api/schemas.py:174` (classe `ChatResponse`)

- [ ] **Step 1: Substituir o `ChatResponse` mínimo pelos schemas completos**

Em `backend/app/api/schemas.py`, substituir o bloco final (a classe `ChatResponse` atual de 2 linhas) por:

```python
class ProposedAction(BaseModel):
    tipo: str  # "gerar_minuta" | "marcar_prazo_cumprido" | "aprovar_peticao"
    label: str
    endpoint: str
    metodo: str = "POST"
    payload: dict


class ToolTraceItem(BaseModel):
    ferramenta: str
    input: dict


class ChatResponse(BaseModel):
    reply: str
    proposed_actions: list[ProposedAction] = []
    tool_trace: list[ToolTraceItem] = []
```

- [ ] **Step 2: Verificar import**

`ChatRequest`, `ChatMessage`, `AuditLogOut` já existem no arquivo (linhas 152-171). Confirme que `BaseModel` e `ConfigDict` já estão importados no topo (estão — linha 7). Nenhum import novo é necessário.

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/schemas.py
git commit -m "feat: chat schemas for agentic proposed actions"
```

---

### Task 2: Endpoint GET /audit (trilha imutável legível)

**Files:**
- Modify: `backend/app/api/main.py` (import de `AuditLogOut`; nova rota perto de `dashboard_operacional`)
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Escrever o teste que falha**

Adicionar ao fim de `backend/tests/test_api.py`:

```python
def test_listar_auditoria_filtra_por_entidade(client, db_session, seeded):
    db_session.add_all(
        [
            models.AuditLog(ator="usuario:1", acao="prazo_revisado", entidade="prazo", entidade_id=1),
            models.AuditLog(ator="system", acao="captura_oab_executada", entidade="escritorio", entidade_id=1),
        ]
    )
    db_session.flush()

    todos = client.get("/audit").json()
    assert len(todos) == 2
    # mais recente primeiro
    assert todos[0]["acao"] in {"prazo_revisado", "captura_oab_executada"}

    so_prazo = client.get("/audit", params={"entidade": "prazo"}).json()
    assert len(so_prazo) == 1
    assert so_prazo[0]["entidade"] == "prazo"
    assert so_prazo[0]["ator"] == "usuario:1"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_api.py::test_listar_auditoria_filtra_por_entidade -v`
Expected: FAIL com 404 (rota inexistente).

- [ ] **Step 3: Adicionar o import do schema**

Em `backend/app/api/main.py`, no bloco `from app.api.schemas import (` (linha 18), adicionar `AuditLogOut,` em ordem alfabética (antes de `ApprovePeticaoRequest,`):

```python
from app.api.schemas import (
    AuditLogOut,
    ApprovePeticaoRequest,
    CaptureDemoRequest,
```

- [ ] **Step 4: Adicionar a rota**

Em `backend/app/api/main.py`, logo após o fim da função `dashboard_operacional` (depois do `return OperationalDashboard(...)`, antes de `@app.post("/capture/demo"...)`), inserir:

```python
    @app.get("/audit", response_model=list[AuditLogOut])
    def listar_auditoria(
        session: Session = Depends(get_session),
        entidade: str | None = Query(default=None),
        entidade_id: int | None = Query(default=None),
        limit: int = Query(default=100, le=500),
    ) -> list[models.AuditLog]:
        stmt = select(models.AuditLog)
        if entidade is not None:
            stmt = stmt.where(models.AuditLog.entidade == entidade)
        if entidade_id is not None:
            stmt = stmt.where(models.AuditLog.entidade_id == entidade_id)
        stmt = stmt.order_by(models.AuditLog.id.desc()).limit(limit)
        return list(session.scalars(stmt))
```

- [ ] **Step 5: Rodar e ver passar**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_api.py::test_listar_auditoria_filtra_por_entidade -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/main.py backend/tests/test_api.py
git commit -m "feat: read-only GET /audit endpoint with entity filters"
```

---

### Task 3: Registry de ferramentas do chat (leitura executa, ação é declarada)

Cria um módulo separado, testável isolado, com (a) as definições JSON das ferramentas para o Claude e (b) o executor das ferramentas de leitura contra o SOR. As ferramentas de ação são declaradas mas **não** têm executor.

**Files:**
- Create: `backend/app/agent/chat_tools.py`
- Test: `backend/tests/test_chat_tools.py`

- [ ] **Step 1: Escrever os testes que falham**

Criar `backend/tests/test_chat_tools.py`:

```python
"""Tests for the chat agent tool registry."""

from datetime import date

import pytest

from app.agent import chat_tools
from app.sor import models


@pytest.fixture
def seeded(db_session):
    esc = models.Escritorio(nome="Escritorio Teste")
    db_session.add(esc)
    db_session.flush()
    proc = models.Processo(escritorio_id=esc.id, numero="1009988-77.2026.8.26.0100", sistema="e-SAJ")
    db_session.add(proc)
    db_session.flush()
    intim = models.Intimacao(
        processo_id=proc.id, fonte="DJEN", fonte_id="x1",
        numero_processo=proc.numero, tipo_comunicacao="Intimacao para replica",
        teor="Apresente replica em 15 dias.", data_disponibilizacao=date(2026, 6, 1),
    )
    db_session.add(intim)
    db_session.flush()
    prazo = models.Prazo(
        processo_id=proc.id, intimacao_id=intim.id, descricao="Replica",
        data_inicio=date(2026, 6, 2), dias=15, dias_uteis=True,
        data_fatal=date(2026, 6, 23), cumprido=False,
    )
    db_session.add(prazo)
    db_session.flush()
    return {"processo": proc, "intimacao": intim, "prazo": prazo}


def test_tool_definitions_expoem_leitura_e_acao_mas_nunca_protocolar():
    names = {t["name"] for t in chat_tools.TOOL_DEFINITIONS}
    assert {"listar_prazos", "buscar_processo", "ler_intimacao"} <= names
    assert {"gerar_minuta", "marcar_prazo_cumprido", "aprovar_peticao"} <= names
    # gate: protocolar jamais é uma ferramenta exposta ao modelo
    assert not any("protocol" in n for n in names)


def test_acao_e_leitura_estao_corretamente_classificadas():
    assert chat_tools.is_action_tool("gerar_minuta")
    assert chat_tools.is_action_tool("aprovar_peticao")
    assert not chat_tools.is_action_tool("listar_prazos")


def test_executar_ferramenta_leitura_listar_prazos(db_session, seeded):
    out = chat_tools.execute_read_tool(db_session, "listar_prazos", {})
    assert "Replica" in out
    assert "2026-06-23" in out


def test_executar_ferramenta_leitura_ler_intimacao_filtra_segredos(db_session, seeded):
    out = chat_tools.execute_read_tool(
        db_session, "ler_intimacao", {"intimacao_id": seeded["intimacao"].id}
    )
    assert "replica" in out.lower()
    assert seeded["processo"].numero in out


def test_acao_proposta_constroi_endpoint_e_payload(seeded):
    action = chat_tools.build_proposed_action(
        "gerar_minuta", {"intimacao_id": seeded["intimacao"].id}
    )
    assert action["endpoint"] == f"/intimacoes/{seeded['intimacao'].id}/draft"
    assert action["tipo"] == "gerar_minuta"
    assert action["metodo"] == "POST"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_chat_tools.py -v`
Expected: FAIL com `ModuleNotFoundError: app.agent.chat_tools`.

- [ ] **Step 3: Implementar o módulo**

Criar `backend/app/agent/chat_tools.py`:

```python
"""Tool registry for the agentic chat assistant.

Read tools execute against the SOR and return text the model reads. Action
tools are *declared* to the model but never executed here — the API layer
intercepts them as proposed actions for the human-approval gate. ``protocolar``
is deliberately absent: filing is never an agent tool.

Only non-sensitive fields ever reach the model output; we whitelist what each
read tool serializes rather than dumping ORM objects.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.sor import models

# ---- tool definitions sent to Claude -----------------------------------------

_READ_TOOLS = [
    {
        "name": "listar_prazos",
        "description": (
            "Lista os prazos do escritório (data fatal, dias, se cumprido). "
            "Use para responder sobre prazos pendentes, vencidos ou próximos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "apenas_pendentes": {
                    "type": "boolean",
                    "description": "Se true, retorna só os não cumpridos.",
                }
            },
        },
    },
    {
        "name": "buscar_processo",
        "description": (
            "Busca um processo pelo número CNJ ou id e resume sua situação "
            "(classe, tribunal, sistema, prazos)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "numero": {"type": "string", "description": "Número CNJ do processo."},
                "processo_id": {"type": "integer", "description": "Id interno do processo."},
            },
        },
    },
    {
        "name": "ler_intimacao",
        "description": "Lê o teor e os metadados de uma intimação pelo id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "intimacao_id": {"type": "integer", "description": "Id da intimação."}
            },
            "required": ["intimacao_id"],
        },
    },
]

_ACTION_TOOLS = [
    {
        "name": "gerar_minuta",
        "description": (
            "Propõe gerar a minuta (rascunho de petição) para uma intimação. "
            "NÃO executa: o advogado confirma antes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"intimacao_id": {"type": "integer"}},
            "required": ["intimacao_id"],
        },
    },
    {
        "name": "marcar_prazo_cumprido",
        "description": "Propõe marcar um prazo como cumprido. NÃO executa: o advogado confirma.",
        "input_schema": {
            "type": "object",
            "properties": {"prazo_id": {"type": "integer"}},
            "required": ["prazo_id"],
        },
    },
    {
        "name": "aprovar_peticao",
        "description": (
            "Propõe aprovar uma petição (gate OAB), liberando-a para protocolo. "
            "NÃO executa: o advogado confirma. Nunca protocola."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"peticao_id": {"type": "integer"}},
            "required": ["peticao_id"],
        },
    },
]

TOOL_DEFINITIONS = _READ_TOOLS + _ACTION_TOOLS
_ACTION_NAMES = frozenset(t["name"] for t in _ACTION_TOOLS)


def is_action_tool(name: str) -> bool:
    return name in _ACTION_NAMES


# ---- read tool execution -----------------------------------------------------


def _prazo_dict(prazo: models.Prazo) -> dict:
    return {
        "id": prazo.id,
        "descricao": prazo.descricao,
        "data_fatal": prazo.data_fatal.isoformat(),
        "dias": prazo.dias,
        "dias_uteis": prazo.dias_uteis,
        "cumprido": prazo.cumprido,
        "processo_id": prazo.processo_id,
        "intimacao_id": prazo.intimacao_id,
    }


def execute_read_tool(session: Session, name: str, tool_input: dict) -> str:
    """Run a read tool and return a JSON string the model can consume."""
    if name == "listar_prazos":
        stmt = select(models.Prazo)
        if tool_input.get("apenas_pendentes"):
            stmt = stmt.where(models.Prazo.cumprido.is_(False))
        stmt = stmt.order_by(models.Prazo.data_fatal.asc()).limit(50)
        prazos = [_prazo_dict(p) for p in session.scalars(stmt)]
        return json.dumps({"prazos": prazos}, ensure_ascii=False)

    if name == "buscar_processo":
        proc = None
        if tool_input.get("processo_id") is not None:
            proc = session.get(models.Processo, tool_input["processo_id"])
        elif tool_input.get("numero"):
            proc = session.scalar(
                select(models.Processo).where(models.Processo.numero == tool_input["numero"])
            )
        if proc is None:
            return json.dumps({"erro": "processo não encontrado"}, ensure_ascii=False)
        prazos = [
            _prazo_dict(p)
            for p in session.scalars(
                select(models.Prazo).where(models.Prazo.processo_id == proc.id)
            )
        ]
        return json.dumps(
            {
                "id": proc.id,
                "numero": proc.numero,
                "classe": proc.classe,
                "tribunal": proc.tribunal,
                "orgao_julgador": proc.orgao_julgador,
                "sistema": proc.sistema,
                "prazos": prazos,
            },
            ensure_ascii=False,
        )

    if name == "ler_intimacao":
        intim = session.get(models.Intimacao, tool_input.get("intimacao_id"))
        if intim is None:
            return json.dumps({"erro": "intimação não encontrada"}, ensure_ascii=False)
        return json.dumps(
            {
                "id": intim.id,
                "numero_processo": intim.numero_processo,
                "tribunal": intim.tribunal,
                "tipo_comunicacao": intim.tipo_comunicacao,
                "teor": intim.teor,
                "data_disponibilizacao": (
                    intim.data_disponibilizacao.isoformat()
                    if intim.data_disponibilizacao
                    else None
                ),
            },
            ensure_ascii=False,
        )

    return json.dumps({"erro": f"ferramenta de leitura desconhecida: {name}"}, ensure_ascii=False)


# ---- action proposals (never executed here) ----------------------------------

_ACTION_ENDPOINTS = {
    "gerar_minuta": lambda i: f"/intimacoes/{i['intimacao_id']}/draft",
    "marcar_prazo_cumprido": lambda i: f"/prazos/{i['prazo_id']}/cumprir",
    "aprovar_peticao": lambda i: f"/peticoes/{i['peticao_id']}/approve",
}

_ACTION_LABELS = {
    "gerar_minuta": "Gerar minuta",
    "marcar_prazo_cumprido": "Marcar prazo como cumprido",
    "aprovar_peticao": "Aprovar petição (gate OAB)",
}


def build_proposed_action(name: str, tool_input: dict) -> dict:
    """Build the front-end-facing proposal for an action tool call."""
    return {
        "tipo": name,
        "label": _ACTION_LABELS[name],
        "endpoint": _ACTION_ENDPOINTS[name](tool_input),
        "metodo": "POST",
        "payload": dict(tool_input),
    }
```

- [ ] **Step 4: Rodar e ver passar**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_chat_tools.py -v`
Expected: PASS (todos os 5 testes).

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/chat_tools.py backend/tests/test_chat_tools.py
git commit -m "feat: chat agent tool registry (read executes, action proposed)"
```

---

### Task 4: Loop agêntico em assistant.py

Evolui `chat_with_assistant` para um loop de tool-use manual (padrão "Manual Agentic Loop" do SDK, com human-in-the-loop nas ações). Leitura executa; ação é interceptada e devolve um `tool_result` informando que aguarda confirmação, e a ação é coletada para retorno.

**Files:**
- Modify: `backend/app/agent/assistant.py` (reescreve `chat_with_assistant`, mantém whitelist/system)
- Test: `backend/tests/test_assistant.py`

- [ ] **Step 1: Escrever os testes que falham**

Criar `backend/tests/test_assistant.py`:

```python
"""Tests for the agentic chat loop (Anthropic client mocked)."""

from types import SimpleNamespace

from app.agent import assistant


class _Block:
    def __init__(self, type, **kw):
        self.type = type
        for k, v in kw.items():
            setattr(self, k, v)


def _text(t):
    return _Block("text", text=t)


def _tool_use(name, tool_input, id="tu1"):
    return _Block("tool_use", name=name, input=tool_input, id=id)


class FakeClient:
    """Returns queued responses; records the messages it was called with."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        content = self._responses.pop(0)
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        return SimpleNamespace(content=content, stop_reason=stop)


def _read_tool(session, name, tool_input):
    return f"RESULT::{name}"


def test_loop_executa_ferramenta_de_leitura_e_responde():
    client = FakeClient(
        [
            [_tool_use("listar_prazos", {})],          # 1ª resposta: pede leitura
            [_text("Você tem 1 prazo pendente.")],     # 2ª resposta: texto final
        ]
    )
    result = assistant.chat_with_assistant(
        [{"role": "user", "content": "Quais meus prazos?"}],
        client=client,
        session=object(),
        read_tool_runner=_read_tool,
    )
    assert result["reply"] == "Você tem 1 prazo pendente."
    assert result["proposed_actions"] == []
    assert {t["ferramenta"] for t in result["tool_trace"]} == {"listar_prazos"}
    # a leitura virou tool_result na 2ª chamada
    assert any("RESULT::listar_prazos" in str(c["messages"]) for c in client.calls)


def test_loop_intercepta_acao_como_proposta_sem_executar():
    client = FakeClient(
        [
            [_tool_use("gerar_minuta", {"intimacao_id": 7})],
            [_text("Preparei a proposta de minuta para sua confirmação.")],
        ]
    )
    result = assistant.chat_with_assistant(
        [{"role": "user", "content": "Gere a minuta da intimação 7"}],
        client=client,
        session=object(),
        read_tool_runner=_read_tool,
    )
    assert len(result["proposed_actions"]) == 1
    action = result["proposed_actions"][0]
    assert action["tipo"] == "gerar_minuta"
    assert action["endpoint"] == "/intimacoes/7/draft"
    assert "confirmação" in result["reply"].lower()


def test_loop_passa_ferramentas_e_nunca_inclui_protocolar():
    client = FakeClient([[_text("ok")]])
    assistant.chat_with_assistant(
        [{"role": "user", "content": "oi"}],
        client=client,
        session=object(),
        read_tool_runner=_read_tool,
    )
    tools = client.calls[0]["tools"]
    names = {t["name"] for t in tools}
    assert "listar_prazos" in names
    assert not any("protocol" in n for n in names)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_assistant.py -v`
Expected: FAIL (assinatura atual de `chat_with_assistant` retorna `str`, não aceita `session`/`read_tool_runner`).

- [ ] **Step 3: Reescrever `chat_with_assistant`**

Em `backend/app/agent/assistant.py`, manter as constantes `_MODEL`, `_ALLOWED_CONTEXT_KEYS`, `_SYSTEM` e a função `_contexto_linhas` como estão. Adicionar o import e **substituir** a função `chat_with_assistant` inteira por:

No topo, junto aos imports existentes, adicionar:

```python
from collections.abc import Callable

from app.agent import chat_tools
```

E substituir a função `chat_with_assistant` (linhas 57-85 do arquivo atual) por:

```python
_MAX_ITERS = 6


def chat_with_assistant(
    messages: list[dict],
    *,
    session,
    read_tool_runner: Callable[[object, str, dict], str] = chat_tools.execute_read_tool,
    contexto_processo: dict | None = None,
    resumo_contexto: str | None = None,
    client: anthropic.Anthropic | None = None,
    model: str = _MODEL,
) -> dict:
    """Run the agentic chat loop.

    Read tools execute against ``session`` via ``read_tool_runner``; action tools
    are intercepted as proposals and never executed here (human-approval gate).
    Returns ``{"reply", "proposed_actions", "tool_trace"}``.
    """
    client = client or anthropic.Anthropic()

    system = _SYSTEM + _contexto_linhas(contexto_processo)
    if resumo_contexto:
        system += f"\n\nResumo operacional disponível:\n{resumo_contexto}"

    convo: list[dict] = list(messages)
    proposed_actions: list[dict] = []
    tool_trace: list[dict] = []
    reply = ""

    for _ in range(_MAX_ITERS):
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=system,
            tools=chat_tools.TOOL_DEFINITIONS,
            messages=convo,
        )

        reply = "".join(b.text for b in response.content if b.type == "text") or reply
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if response.stop_reason != "tool_use" or not tool_uses:
            break

        convo.append({"role": "assistant", "content": response.content})
        results = []
        for block in tool_uses:
            tool_trace.append({"ferramenta": block.name, "input": dict(block.input)})
            if chat_tools.is_action_tool(block.name):
                proposed_actions.append(
                    chat_tools.build_proposed_action(block.name, dict(block.input))
                )
                content = (
                    "Proposta registrada e enviada ao advogado para confirmação. "
                    "Não execute; aguarde a aprovação humana."
                )
            else:
                content = read_tool_runner(session, block.name, dict(block.input))
            results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": content}
            )
        convo.append({"role": "user", "content": results})

    return {"reply": reply, "proposed_actions": proposed_actions, "tool_trace": tool_trace}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_assistant.py -v`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/assistant.py backend/tests/test_assistant.py
git commit -m "feat: agentic tool-use loop in chat assistant with action interception"
```

---

### Task 5: Endpoint POST /chat

Liga o loop ao SOR e devolve `ChatResponse`. Erro de IA → 503 (mesmo padrão de `gerar_minuta`).

**Files:**
- Modify: `backend/app/api/main.py` (imports + nova rota)
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao fim de `backend/tests/test_api.py`:

```python
def test_chat_retorna_reply_e_propostas(client, db_session, seeded, monkeypatch):
    def fake_chat(messages, *, session, **kwargs):
        return {
            "reply": "Você tem 1 prazo pendente; quer gerar a minuta?",
            "proposed_actions": [
                {
                    "tipo": "gerar_minuta",
                    "label": "Gerar minuta",
                    "endpoint": "/intimacoes/1/draft",
                    "metodo": "POST",
                    "payload": {"intimacao_id": 1},
                }
            ],
            "tool_trace": [{"ferramenta": "listar_prazos", "input": {}}],
        }

    monkeypatch.setattr("app.api.main.chat_with_assistant", fake_chat)
    resp = client.post("/chat", json={"messages": [{"role": "user", "content": "meus prazos?"}]})

    assert resp.status_code == 200
    body = resp.json()
    assert "prazo" in body["reply"].lower()
    assert body["proposed_actions"][0]["tipo"] == "gerar_minuta"
    assert body["tool_trace"][0]["ferramenta"] == "listar_prazos"


def test_chat_falha_de_ia_retorna_503(client, db_session, seeded, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("anthropic indisponivel")

    monkeypatch.setattr("app.api.main.chat_with_assistant", boom)
    resp = client.post("/chat", json={"messages": [{"role": "user", "content": "oi"}]})
    assert resp.status_code == 503
    assert "assistente" in resp.json()["detail"].lower()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_api.py::test_chat_retorna_reply_e_propostas tests/test_api.py::test_chat_falha_de_ia_retorna_503 -v`
Expected: FAIL com 404.

- [ ] **Step 3: Adicionar imports**

Em `backend/app/api/main.py`:

No bloco `from app.api.schemas import (`, adicionar `ChatRequest,` e `ChatResponse,` (ordem alfabética, após `CaptureResultOut,`):

```python
    CaptureResultOut,
    ChatRequest,
    ChatResponse,
    DraftRequest,
```

E após a linha `from app.agent.service import MissingIntimationTextError, draft_from_intimacao` (linha 17), adicionar:

```python
from app.agent.assistant import chat_with_assistant
```

- [ ] **Step 4: Adicionar a rota**

Em `backend/app/api/main.py`, antes de `return app` (final de `create_app`), inserir:

```python
    @app.post("/chat", response_model=ChatResponse)
    def chat(
        payload: ChatRequest,
        session: Session = Depends(get_session),
    ) -> ChatResponse:
        contexto = None
        if payload.processo_id is not None:
            proc = session.get(models.Processo, payload.processo_id)
            if proc is not None:
                contexto = {
                    "numero": proc.numero,
                    "classe": proc.classe,
                    "tribunal": proc.tribunal,
                    "orgao_julgador": proc.orgao_julgador,
                    "sistema": proc.sistema,
                }
        try:
            result = chat_with_assistant(
                [m.model_dump() for m in payload.messages],
                session=session,
                contexto_processo=contexto,
            )
        except Exception as exc:  # noqa: BLE001 - chamada de IA pode falhar
            raise HTTPException(
                status_code=503,
                detail=f"assistente indisponível: {exc}",
            ) from exc
        return ChatResponse(**result)
```

- [ ] **Step 5: Rodar e ver passar (e a suíte toda)**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (toda a suíte verde, incluindo os 2 novos).

- [ ] **Step 6: Lint**

Run: `./.venv/Scripts/python.exe -m ruff check .`
Expected: limpo. Corrija ordem de imports se o ruff reclamar.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/main.py backend/tests/test_api.py
git commit -m "feat: POST /chat endpoint wiring the agentic assistant"
```

---

### Task 6: Camada de API do frontend

Adiciona as funções que faltam em `lib/api.ts` e faz `gerarMinuta` retornar a classificação.

**Files:**
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Adicionar os tipos do chat e auditoria**

No topo de `frontend/lib/api.ts`, após o tipo `ReviewQueueItem` (linha 92), adicionar:

```typescript
export type ProposedAction = {
  tipo: string;
  label: string;
  endpoint: string;
  metodo: string;
  payload: Record<string, unknown>;
};

export type ChatTurn = { role: "user" | "assistant"; content: string };

export type ChatResponse = {
  reply: string;
  proposed_actions: ProposedAction[];
  tool_trace: { ferramenta: string; input: Record<string, unknown> }[];
};

export type AuditLog = {
  id: number;
  ator: string;
  acao: string;
  entidade: string | null;
  entidade_id: number | null;
  detalhe: Record<string, unknown> | null;
  created_at: string;
};

export type Classificacao = {
  tipo: string;
  peticao_sugerida: string;
  prazo_dias: number;
  dias_uteis: boolean;
  confianca: number;
  resumo: string;
};
```

- [ ] **Step 2: `gerarMinuta` retorna a classificação**

Substituir a função `gerarMinuta` (linhas 357-363) por:

```typescript
export async function gerarMinuta(intimacaoId: number): Promise<Classificacao | null> {
  if (demoDashboard.intimacoes.some((item) => item.id === intimacaoId)) return null;
  const resp = await request<{ classificacao: Classificacao }>(
    `/intimacoes/${intimacaoId}/draft`,
    { method: "POST", body: JSON.stringify({}) }
  );
  return resp.classificacao;
}
```

- [ ] **Step 3: Adicionar as novas funções**

Ao fim de `frontend/lib/api.ts`, adicionar:

```typescript
export async function enviarMensagemChat(
  messages: ChatTurn[],
  processoId?: number
): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ messages, processo_id: processoId ?? null })
  });
}

export async function rodarCapturaOab(
  oab: string,
  uf: string
): Promise<CaptureResult> {
  return request<CaptureResult>("/capture/oab", {
    method: "POST",
    body: JSON.stringify({ oab, uf })
  });
}

export async function revisarPrazo(
  prazoId: number,
  patch: Partial<Pick<Prazo, "descricao" | "dias" | "dias_uteis" | "data_inicio" | "data_fatal">>
): Promise<Prazo> {
  return request<Prazo>(`/prazos/${prazoId}`, {
    method: "PATCH",
    body: JSON.stringify({ usuario_id: 1, ...patch })
  });
}

export async function carregarAuditoria(filtros?: {
  entidade?: string;
  entidade_id?: number;
}): Promise<AuditLog[]> {
  const params = new URLSearchParams();
  if (filtros?.entidade) params.set("entidade", filtros.entidade);
  if (filtros?.entidade_id != null) params.set("entidade_id", String(filtros.entidade_id));
  const qs = params.toString();
  return request<AuditLog[]>(`/audit${qs ? `?${qs}` : ""}`);
}
```

- [ ] **Step 4: Verificar a compilação**

Run (de `/frontend`): `npx tsc --noEmit`
Expected: sem erros novos em `lib/api.ts`. (Pode haver erro em `page.tsx` por causa do retorno mudado de `gerarMinuta` — será resolvido na Task 10.)

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat: frontend api layer for chat, oab capture, prazo revision, audit"
```

---

### Task 7: Painel do assistente (chat agêntico)

Componente dockável à direita com histórico local, input e render das `proposed_actions` como cards de confirmação.

**Files:**
- Create: `frontend/app/AssistantPanel.tsx`
- Modify: `frontend/app/page.tsx` (montar o painel)

- [ ] **Step 1: Criar o componente**

Criar `frontend/app/AssistantPanel.tsx`:

```typescript
"use client";

import { Bot, Loader2, Send, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { ChatTurn, enviarMensagemChat, ProposedAction } from "@/lib/api";

type Props = {
  processoId?: number;
  offline: boolean;
  onConfirmAction: (action: ProposedAction) => Promise<void>;
  onClose: () => void;
};

export default function AssistantPanel({
  processoId,
  offline,
  onConfirmAction,
  onClose
}: Props) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState<ProposedAction[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    const next: ChatTurn[] = [...turns, { role: "user", content: text }];
    setTurns(next);
    setInput("");
    setBusy(true);
    setError(null);
    try {
      const resp = await enviarMensagemChat(next, processoId);
      setTurns([...next, { role: "assistant", content: resp.reply }]);
      setPending(resp.proposed_actions);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no assistente");
    } finally {
      setBusy(false);
    }
  }

  async function confirm(action: ProposedAction) {
    setBusy(true);
    setError(null);
    try {
      await onConfirmAction(action);
      setPending((prev) => prev.filter((a) => a !== action));
      setTurns((prev) => [
        ...prev,
        { role: "assistant", content: `Ação executada: ${action.label}.` }
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ação não concluída");
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="assistantPanel">
      <header className="assistantHead">
        <div>
          <Bot size={16} /> <strong>Assistente Causor</strong>
        </div>
        <button className="iconButton" onClick={onClose} title="Fechar">
          <X size={15} />
        </button>
      </header>

      <div className="assistantBody">
        {turns.length === 0 ? (
          <p className="assistantHint">
            Pergunte sobre prazos, intimações ou peça uma ação (gerar minuta,
            marcar prazo). Ações irreversíveis sempre passam pela sua confirmação.
          </p>
        ) : null}
        {turns.map((turn, i) => (
          <div key={i} className={`chatTurn ${turn.role}`}>
            <span>{turn.content}</span>
          </div>
        ))}

        {pending.map((action, i) => (
          <div className="proposedAction" key={`${action.tipo}-${i}`}>
            <div>
              <ShieldCheck size={14} /> <strong>{action.label}</strong>
              <small>{action.endpoint}</small>
            </div>
            <div className="proposedActions">
              <button
                className="toolbarButton primary"
                disabled={busy || offline}
                onClick={() => confirm(action)}
              >
                Confirmar
              </button>
              <button
                className="toolbarButton"
                disabled={busy}
                onClick={() => setPending((prev) => prev.filter((a) => a !== action))}
              >
                Descartar
              </button>
            </div>
          </div>
        ))}

        {error ? <div className="assistantError">{error}</div> : null}
      </div>

      <footer className="assistantFoot">
        <input
          placeholder={offline ? "Backend offline" : "Pergunte ao assistente…"}
          value={input}
          disabled={offline || busy}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void send();
          }}
        />
        <button className="iconButton" disabled={offline || busy} onClick={() => void send()}>
          {busy ? <Loader2 className="spin" size={15} /> : <Send size={15} />}
        </button>
      </footer>
    </aside>
  );
}
```

> Nota: remova as duas linhas `request as _unused` / `void _unused;` — foram um lembrete; o componente não precisa de `request`. O bloco de import correto é:
> ```typescript
> import { ChatTurn, enviarMensagemChat, ProposedAction } from "@/lib/api";
> ```

- [ ] **Step 2: Montar o painel no `page.tsx`**

Em `frontend/app/page.tsx`:

(a) No import de `lucide-react`, garantir que `MessageCircle` já está importado (está). Adicionar ao import de `@/lib/api` o tipo/funcão necessários:

Trocar o bloco `import { ... } from "@/lib/api";` (linhas 33-45) para incluir `ProposedAction` e `request`-free helpers usados na confirmação — adicione `enviarMensagemChat` não é necessário aqui; o que precisamos é executar a ação confirmada. Adicione ao bloco existente: `ProposedAction,` e as três funções de ação já importadas (`aprovarPeticao`, `cumprirPrazo`, `gerarMinuta` já estão).

Import adicional logo abaixo dos imports de `@/lib/api`:

```typescript
import AssistantPanel from "./AssistantPanel";
```

(b) Dentro de `Home()`, após `const [captureResult, setCaptureResult] = useState...` (linha 116), adicionar:

```typescript
  const [assistantOpen, setAssistantOpen] = useState(false);
```

(c) Adicionar o handler de confirmação dentro de `Home()` (após `runCapture`):

```typescript
  async function confirmAssistantAction(action: ProposedAction) {
    const id = Number(
      action.payload.intimacao_id ?? action.payload.prazo_id ?? action.payload.peticao_id
    );
    if (action.tipo === "gerar_minuta") await gerarMinuta(id);
    else if (action.tipo === "marcar_prazo_cumprido") await cumprirPrazo(id);
    else if (action.tipo === "aprovar_peticao") await aprovarPeticao(id);
    await refresh();
  }
```

(d) Adicionar um botão "Assistente" na `appActions` do header (após o botão "Rodar captura", linha ~324):

```tsx
            <button
              className="toolbarButton"
              onClick={() => setAssistantOpen((v) => !v)}
            >
              <MessageCircle size={15} />
              Assistente
            </button>
```

(e) Renderizar o painel: imediatamente antes do fechamento `</main>` (linha 601), adicionar:

```tsx
      {assistantOpen ? (
        <AssistantPanel
          offline={offline}
          onConfirmAction={confirmAssistantAction}
          onClose={() => setAssistantOpen(false)}
        />
      ) : null}
```

- [ ] **Step 3: Estilos mínimos**

Adicionar ao fim de `frontend/app/globals.css` (ou ao arquivo de CSS global do projeto — confirme o nome com `Glob frontend/app/*.css`):

```css
.assistantPanel {
  position: fixed;
  top: 0;
  right: 0;
  width: 360px;
  height: 100vh;
  background: #fff;
  border-left: 1px solid #e5e2da;
  display: flex;
  flex-direction: column;
  z-index: 50;
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.06);
}
.assistantHead,
.assistantFoot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid #eee;
}
.assistantFoot {
  border-top: 1px solid #eee;
  border-bottom: none;
}
.assistantFoot input {
  flex: 1;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 8px;
}
.assistantBody {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.chatTurn {
  padding: 8px 10px;
  border-radius: 10px;
  max-width: 90%;
}
.chatTurn.user {
  align-self: flex-end;
  background: #f0ede6;
}
.chatTurn.assistant {
  align-self: flex-start;
  background: #f7f6f2;
}
.proposedAction {
  border: 1px solid #e0c98a;
  background: #fbf6e8;
  border-radius: 10px;
  padding: 10px;
}
.proposedActions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.assistantHint {
  color: #888;
  font-size: 13px;
}
.assistantError {
  color: #b00020;
  font-size: 13px;
}
```

- [ ] **Step 4: Compilar**

Run (de `/frontend`): `npx tsc --noEmit`
Expected: sem erros.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/AssistantPanel.tsx frontend/app/page.tsx frontend/app/globals.css
git commit -m "feat: agentic assistant panel with confirm-gated action cards"
```

---

### Task 8: Captura real por OAB (modal)

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Estado e handler**

Em `Home()`, junto aos demais `useState`, adicionar:

```typescript
  const [oabForm, setOabForm] = useState<{ open: boolean; oab: string; uf: string }>({
    open: false,
    oab: "",
    uf: "SP"
  });
```

Adicionar import de `rodarCapturaOab` ao bloco `@/lib/api` (junto a `rodarCapturaDemo`).

Adicionar o handler após `runCapture`:

```typescript
  async function runCaptureOab() {
    setBusy("capture");
    setError(null);
    setCaptureResult(null);
    try {
      const result = await rodarCapturaOab(oabForm.oab.trim(), oabForm.uf.trim());
      setCaptureResult(result);
      setOabForm((f) => ({ ...f, open: false }));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Captura por OAB não concluída");
    } finally {
      setBusy(null);
    }
  }
```

- [ ] **Step 2: Botão + modal**

No header `appActions`, após o botão "Rodar captura", adicionar:

```tsx
            <button
              className="toolbarButton"
              onClick={() => setOabForm((f) => ({ ...f, open: true }))}
              disabled={offline}
            >
              <Search size={15} />
              Captura por OAB
            </button>
```

Antes do fechamento `</section>` da `workspace` (perto do final, antes de `</section>` que fecha `.workspace`), adicionar o modal:

```tsx
        {oabForm.open ? (
          <div className="modalOverlay" onClick={() => setOabForm((f) => ({ ...f, open: false }))}>
            <div className="modalCard" onClick={(e) => e.stopPropagation()}>
              <h3>Captura por OAB</h3>
              <label>
                OAB
                <input
                  value={oabForm.oab}
                  onChange={(e) => setOabForm((f) => ({ ...f, oab: e.target.value }))}
                  placeholder="123456"
                />
              </label>
              <label>
                UF
                <input
                  value={oabForm.uf}
                  maxLength={2}
                  onChange={(e) => setOabForm((f) => ({ ...f, uf: e.target.value.toUpperCase() }))}
                />
              </label>
              <div className="modalActions">
                <button className="toolbarButton" onClick={() => setOabForm((f) => ({ ...f, open: false }))}>
                  Cancelar
                </button>
                <button
                  className="toolbarButton primary"
                  disabled={!oabForm.oab.trim() || busy === "capture"}
                  onClick={() => void runCaptureOab()}
                >
                  {busy === "capture" ? <Loader2 className="spin" size={15} /> : null}
                  Capturar
                </button>
              </div>
            </div>
          </div>
        ) : null}
```

- [ ] **Step 3: Estilos do modal**

Adicionar ao CSS global:

```css
.modalOverlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 60;
}
.modalCard {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.modalCard label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}
.modalCard input {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 8px;
}
.modalActions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
```

- [ ] **Step 4: Compilar e commitar**

Run (de `/frontend`): `npx tsc --noEmit` → sem erros.

```bash
git add frontend/app/page.tsx frontend/app/globals.css
git commit -m "feat: real OAB capture modal wired to POST /capture/oab"
```

---

### Task 9: Painel de Auditoria

**Files:**
- Create: `frontend/app/AuditPanel.tsx`
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Criar o componente**

Criar `frontend/app/AuditPanel.tsx`:

```typescript
"use client";

import { Table2 } from "lucide-react";
import { useEffect, useState } from "react";
import { AuditLog, carregarAuditoria } from "@/lib/api";

export default function AuditPanel({ offline }: { offline: boolean }) {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (offline) return;
    carregarAuditoria()
      .then(setLogs)
      .catch((err) => setError(err instanceof Error ? err.message : "Falha ao carregar auditoria"));
  }, [offline]);

  return (
    <section className="panel">
      <header>
        <h2>
          <Table2 size={15} /> Auditoria
        </h2>
        <span>trilha imutável</span>
      </header>
      {error ? <div className="assistantError">{error}</div> : null}
      <div className="auditList">
        {logs.map((log) => (
          <article className="auditItem" key={log.id}>
            <div>
              <strong>{log.acao}</strong>
              <span>
                {log.ator} · {log.entidade ?? "-"}
                {log.entidade_id != null ? ` #${log.entidade_id}` : ""}
              </span>
            </div>
          </article>
        ))}
        {!logs.length && !error ? <div className="empty">Sem eventos registrados</div> : null}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Montar no `page.tsx`**

Adicionar o import:

```typescript
import AuditPanel from "./AuditPanel";
```

Na `bottomGrid` (linha ~538), trocar o painel estático "Auditoria e segurança" por uma combinação: manter o painel de sinais e adicionar o `AuditPanel` ao lado. Concretamente, dentro de `<section className="bottomGrid">`, após o `<Panel title="Auditoria e segurança" ...>...</Panel>`, adicionar:

```tsx
          <AuditPanel offline={offline} />
```

- [ ] **Step 3: Compilar e commitar**

Run (de `/frontend`): `npx tsc --noEmit` → sem erros.

```bash
git add frontend/app/AuditPanel.tsx frontend/app/page.tsx
git commit -m "feat: audit panel reading GET /audit"
```

---

### Task 9b: Revisão de prazo inline (UI do PATCH /prazos)

Fecha o bucket D do spec: um botão na linha do prazo que permite ajustar a data fatal, chamando `revisarPrazo` (já criado na Task 6). Edição mínima via `prompt` — suficiente para o MVP interno; a auditoria registra `prazo_revisado` no nome do usuário.

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Adicionar `revisarPrazo` ao import de `@/lib/api`**

No bloco `import { ... } from "@/lib/api";` em `frontend/app/page.tsx`, adicionar `revisarPrazo,` (ordem alfabética).

- [ ] **Step 2: Handler de revisão**

Dentro de `Home()`, após `confirmAssistantAction` (Task 7), adicionar:

```typescript
  async function editarPrazo(prazo: Prazo) {
    const atual = prazo.data_fatal;
    const nova = window.prompt(
      `Nova data fatal para "${prazo.descricao ?? "prazo"}" (AAAA-MM-DD):`,
      atual
    );
    if (!nova || nova === atual) return;
    await runAction(`edit-${prazo.id}`, async () => {
      await revisarPrazo(prazo.id, { data_fatal: nova });
    });
  }
```

- [ ] **Step 3: Botão na linha do prazo**

Na `rowActions` da tabela (após o botão "Marcar prazo cumprido", linha ~499), adicionar:

```tsx
                      <button
                        className="iconButton"
                        title="Editar data fatal"
                        disabled={!prazo || busy === `edit-${prazo?.id}` || offline}
                        onClick={() => (prazo ? void editarPrazo(prazo) : undefined)}
                      >
                        {busy === `edit-${prazo?.id}` ? (
                          <Loader2 className="spin" size={15} />
                        ) : (
                          <CalendarDays size={15} />
                        )}
                      </button>
```

> `CalendarDays` já está importado de `lucide-react` (linha 6).

- [ ] **Step 4: Compilar e commitar**

Run (de `/frontend`): `npx tsc --noEmit` → sem erros.

```bash
git add frontend/app/page.tsx
git commit -m "feat: inline prazo deadline revision via PATCH /prazos"
```

---

### Task 10: Surfacing da classificação de IA

Mostra tipo + confiança da minuta após `gerarMinuta`.

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Estado da última classificação**

Em `Home()`, adicionar:

```typescript
  const [lastClassificacao, setLastClassificacao] = useState<{
    intimacaoId: number;
    tipo: string;
    confianca: number;
  } | null>(null);
```

- [ ] **Step 2: Capturar o retorno de `gerarMinuta`**

A ação de minuta hoje passa por `runAction(...)` que descarta o retorno. Trocar o `onClick` do botão "Gerar minuta" (linha ~474) por um handler dedicado:

```tsx
                        onClick={() =>
                          runAction(`draft-${intimacao.id}`, async () => {
                            const cls = await gerarMinuta(intimacao.id);
                            if (cls)
                              setLastClassificacao({
                                intimacaoId: intimacao.id,
                                tipo: cls.tipo,
                                confianca: cls.confianca
                              });
                          })
                        }
```

> `runAction` aceita `() => Promise<void>`; a função async acima resolve para `void`. OK.

- [ ] **Step 3: Renderizar o badge**

Logo após o bloco `{captureResult ? (...) : null}` (linha ~366), adicionar:

```tsx
        {lastClassificacao ? (
          <div className="notice success">
            <Sparkles size={18} />
            <span>
              Minuta classificada pela IA: <strong>{lastClassificacao.tipo}</strong> ·
              confiança {Math.round(lastClassificacao.confianca * 100)}%
            </span>
          </div>
        ) : null}
```

- [ ] **Step 4: Compilar e commitar**

Run (de `/frontend`): `npx tsc --noEmit` → sem erros (resolve também o erro pendente da Task 6 por causa do retorno mudado de `gerarMinuta`).

```bash
git add frontend/app/page.tsx
git commit -m "feat: surface AI classification + confidence after drafting"
```

---

### Task 11: Verificação final end-to-end

**Files:** nenhum (verificação).

- [ ] **Step 1: Suíte backend verde**

Run (de `/backend`): `./.venv/Scripts/python.exe -m pytest -q`
Expected: tudo PASS.

- [ ] **Step 2: Lint backend**

Run: `./.venv/Scripts/python.exe -m ruff check .`
Expected: limpo.

- [ ] **Step 3: Type-check frontend**

Run (de `/frontend`): `npx tsc --noEmit`
Expected: sem erros.

- [ ] **Step 4: Smoke manual (com `ANTHROPIC_API_KEY` setada)**

Subir backend (`uvicorn app.api.main:app --reload`) e frontend (`npm run dev`), então:
- Abrir o painel Assistente, perguntar "quais meus prazos pendentes?" → resposta usa `listar_prazos`.
- Pedir "gere a minuta da intimação X" → aparece card de confirmação; confirmar dispara `/intimacoes/X/draft`.
- "Captura por OAB" → modal → captura real.
- Painel Auditoria lista os eventos (incl. as ações confirmadas via chat, com `ator=usuario:1`).

- [ ] **Step 5: Commit final / finalizar branch**

Invocar a skill `superpowers:finishing-a-development-branch` para decidir merge/PR.
