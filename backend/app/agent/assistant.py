"""Conversational legal-operations assistant via Gemini.

A ChatGPT-style assistant the lawyer can talk to about a case, a deadline, or
general Brazilian procedural questions. It *reasons and explains* — it never
files anything (that stays behind the human-approval gate) and it never sees
secrets.

This assistant runs on Google Gemini (free tier friendly); the drafter and
classifier stay on Claude. Tool definitions live provider-neutrally in
``chat_tools`` (JSON schema) and are converted to Gemini function declarations
here, so the registry and the human-approval gate are shared and untouched.

Like the drafter, only non-sensitive context may reach the prompt. Certificates,
``.pfx`` passwords and signing credentials live in the vault and must never enter
a prompt or log — so we whitelist the process fields we inject rather than dump
an object.
"""

from __future__ import annotations

from collections.abc import Callable

from google import genai

from app.agent import chat_tools

_MODEL = "gemini-2.5-flash"

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

_MAX_ITERS = 6


def _contexto_linhas(contexto_processo: dict | None) -> str:
    if not contexto_processo:
        return ""
    filtrado = {k: v for k, v in contexto_processo.items() if k in _ALLOWED_CONTEXT_KEYS and v}
    if not filtrado:
        return ""
    linhas = "\n".join(f"- {k}: {v}" for k, v in filtrado.items())
    return f"\n\nProcesso em foco nesta conversa:\n{linhas}"


def _function_declarations() -> list[dict]:
    """Convert the shared tool registry to Gemini function declarations.

    The JSON ``input_schema`` is the same OpenAPI subset Gemini expects, so the
    conversion is a straight rename of the schema key.
    """
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
        }
        for tool in chat_tools.TOOL_DEFINITIONS
    ]


def _to_content(message: dict) -> dict:
    """Map a chat message to a Gemini content (``assistant`` -> ``model``)."""
    role = "model" if message.get("role") == "assistant" else "user"
    return {"role": role, "parts": [{"text": message.get("content", "")}]}


def chat_with_assistant(
    messages: list[dict],
    *,
    session,
    read_tool_runner: Callable[[object, str, dict], str] = chat_tools.execute_read_tool,
    contexto_processo: dict | None = None,
    resumo_contexto: str | None = None,
    client: genai.Client | None = None,
    model: str = _MODEL,
) -> dict:
    """Run the agentic chat loop on Gemini.

    Read tools execute against ``session`` via ``read_tool_runner``; action tools
    are intercepted as proposals and never executed here (human-approval gate).
    Returns ``{"reply", "proposed_actions", "tool_trace"}``.
    """
    client = client or genai.Client()

    system = _SYSTEM + _contexto_linhas(contexto_processo)
    if resumo_contexto:
        system += f"\n\nResumo operacional disponível:\n{resumo_contexto}"

    config = {
        "system_instruction": system,
        "tools": [{"function_declarations": _function_declarations()}],
    }

    convo: list = [_to_content(m) for m in messages]
    proposed_actions: list[dict] = []
    tool_trace: list[dict] = []
    reply = ""

    for _ in range(_MAX_ITERS):
        response = client.models.generate_content(
            model=model, contents=convo, config=config
        )
        parts = response.candidates[0].content.parts or []

        text = "".join(p.text for p in parts if getattr(p, "text", None))
        if text:
            reply = text

        calls = [p.function_call for p in parts if getattr(p, "function_call", None)]
        if not calls:
            break

        # Echo the model turn back, then answer each tool call.
        convo.append(response.candidates[0].content)
        responses: list[dict] = []
        for call in calls:
            args = dict(call.args or {})
            tool_trace.append({"ferramenta": call.name, "input": args})
            if chat_tools.is_action_tool(call.name):
                proposed_actions.append(chat_tools.build_proposed_action(call.name, args))
                content = (
                    "Proposta registrada e enviada ao advogado para confirmação. "
                    "Não execute; aguarde a aprovação humana."
                )
            else:
                content = read_tool_runner(session, call.name, args)
            responses.append(
                {"function_response": {"name": call.name, "response": {"result": content}}}
            )
        convo.append({"role": "user", "parts": responses})

    if not reply:
        reply = (
            "Preparei uma proposta para sua confirmação."
            if proposed_actions
            else "Não consegui elaborar uma resposta. Pode reformular a pergunta?"
        )

    return {"reply": reply, "proposed_actions": proposed_actions, "tool_trace": tool_trace}
