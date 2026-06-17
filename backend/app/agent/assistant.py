"""Conversational legal-operations assistant via Claude.

The assistant uses the shared tool registry. Read tools may query the SOR;
action tools are proposals only and still require human confirmation.
"""

from __future__ import annotations

from collections.abc import Callable

from app.agent import chat_tools
from app.settings import settings

_MAX_ITERS = 6

_ALLOWED_CONTEXT_KEYS = frozenset(
    {
        "numero",
        "classe",
        "tribunal",
        "orgao_julgador",
        "sistema",
        "comarca",
        "vara",
        "polo",
    }
)

_SYSTEM = (
    "Voce e o assistente operacional do Causor, uma plataforma juridica brasileira "
    "para escritorios de advocacia. Ajude o advogado a entender intimacoes, prazos "
    "e andamento dos processos, e a decidir proximos passos. Responda em portugues "
    "claro e objetivo, com rigor tecnico em direito processual brasileiro (CPC/CLT). "
    "Quando citar prazos, lembre que a data fatal oficial e calculada por um motor "
    "deterministico do Causor. Voce nunca protocola nem assina nada: toda acao "
    "irreversivel passa pelo gate OAB. Se nao tiver informacao suficiente, diga isso."
)


def _contexto_linhas(contexto_processo: dict | None) -> str:
    if not contexto_processo:
        return ""
    filtrado = {
        k: v for k, v in contexto_processo.items() if k in _ALLOWED_CONTEXT_KEYS and v
    }
    if not filtrado:
        return ""
    linhas = "\n".join(f"- {k}: {v}" for k, v in filtrado.items())
    return f"\n\nProcesso em foco nesta conversa:\n{linhas}"


def _claude_tools() -> list[dict]:
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": tool["input_schema"],
        }
        for tool in chat_tools.TOOL_DEFINITIONS
    ]


def _to_claude_message(message: dict) -> dict:
    role = "assistant" if message.get("role") == "assistant" else "user"
    return {"role": role, "content": message.get("content", "")}


def chat_with_assistant(
    messages: list[dict],
    *,
    session,
    read_tool_runner: Callable[[object, str, dict], str] = chat_tools.execute_read_tool,
    contexto_processo: dict | None = None,
    resumo_contexto: str | None = None,
    client=None,
    model: str | None = None,
) -> dict:
    """Run the agentic chat loop on Claude."""
    if client is None:
        import anthropic

        client = anthropic.Anthropic()

    system = _SYSTEM + _contexto_linhas(contexto_processo)
    if resumo_contexto:
        system += f"\n\nResumo operacional disponivel:\n{resumo_contexto}"

    convo: list[dict] = [_to_claude_message(m) for m in messages]
    proposed_actions: list[dict] = []
    tool_trace: list[dict] = []
    reply = ""

    for _ in range(_MAX_ITERS):
        response = client.messages.create(
            model=model or settings.claude_chat_model,
            max_tokens=4000,
            system=system,
            messages=convo,
            tools=_claude_tools(),
        )
        text_blocks = [
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ]
        if text_blocks:
            reply = "".join(text_blocks)

        tool_uses = [
            block for block in response.content if getattr(block, "type", None) == "tool_use"
        ]
        if not tool_uses:
            break

        convo.append({"role": "assistant", "content": response.content})
        tool_results: list[dict] = []
        for call in tool_uses:
            args = dict(getattr(call, "input", None) or {})
            tool_trace.append({"ferramenta": call.name, "input": args})
            if chat_tools.is_action_tool(call.name):
                proposed_actions.append(chat_tools.build_proposed_action(call.name, args))
                content = (
                    "Proposta registrada e enviada ao advogado para confirmacao. "
                    "Nao execute; aguarde a aprovacao humana."
                )
            else:
                content = read_tool_runner(session, call.name, args)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": call.id, "content": content}
            )
        convo.append({"role": "user", "content": tool_results})

    if not reply:
        reply = (
            "Preparei uma proposta para sua confirmacao."
            if proposed_actions
            else "Nao consegui elaborar uma resposta. Pode reformular a pergunta?"
        )
    return {"reply": reply, "proposed_actions": proposed_actions, "tool_trace": tool_trace}
