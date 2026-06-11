"""Conversational legal-operations assistant via Claude.

A ChatGPT-style assistant the lawyer can talk to about a case, a deadline, or
general Brazilian procedural questions. It *reasons and explains* — it never
files anything (that stays behind the human-approval gate) and it never sees
secrets.

Like the drafter, only non-sensitive context may reach the prompt. Certificates,
``.pfx`` passwords and signing credentials live in the vault and must never enter
a prompt or log — so we whitelist the process fields we inject rather than dump
an object.
"""

from __future__ import annotations

from collections.abc import Callable

import anthropic

from app.agent import chat_tools

_MODEL = "claude-opus-4-8"

# Only non-sensitive process/intimation metadata may reach the prompt.
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
    "Você é o assistente operacional do Causor, uma plataforma jurídica brasileira para "
    "escritórios de advocacia. Você ajuda o advogado a entender intimações, prazos e o "
    "andamento dos processos, e a decidir os próximos passos. Responda em português claro "
    "e objetivo, com rigor técnico em direito processual brasileiro (CPC/CLT). "
    "Quando citar prazos, lembre que a contagem oficial da data fatal é feita por um motor "
    "determinístico do Causor — você interpreta e orienta, mas não substitui esse cálculo. "
    "Você NUNCA protocola nem assina nada: toda ação irreversível passa pela aprovação humana "
    "do advogado responsável (gate OAB). Se não tiver informação suficiente, diga isso em vez "
    "de inventar. Seja conciso por padrão e aprofunde quando o tema exigir."
)


def _contexto_linhas(contexto_processo: dict | None) -> str:
    if not contexto_processo:
        return ""
    filtrado = {k: v for k, v in contexto_processo.items() if k in _ALLOWED_CONTEXT_KEYS and v}
    if not filtrado:
        return ""
    linhas = "\n".join(f"- {k}: {v}" for k, v in filtrado.items())
    return f"\n\nProcesso em foco nesta conversa:\n{linhas}"


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
