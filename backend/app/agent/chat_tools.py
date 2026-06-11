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
