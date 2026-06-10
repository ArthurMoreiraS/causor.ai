"""Petition drafting via Claude.

The draft is always a *proposal* — it never files anything. Filing passes the
human-approval gate (see the API/peticao status flow). This keeps the lawyer
professionally responsible (OAB).
"""

from __future__ import annotations

import anthropic

from app.agent.classifier import ClassificacaoIntimacao

_MODEL = "claude-opus-4-8"

# Only non-sensitive process metadata may reach the prompt. Secrets
# (certificate passwords, signing credentials) live in the vault and must never
# enter a prompt or log — so we whitelist allowed keys rather than dump a dict.
_ALLOWED_CONTEXT_KEYS = frozenset(
    {"numero", "classe", "tribunal", "orgao_julgador", "comarca", "vara", "cliente", "polo"}
)

_SYSTEM = (
    "Você é um advogado brasileiro redigindo uma minuta de petição. Redija em português "
    "jurídico formal, estruturada (endereçamento, qualificação, fatos, fundamentos, pedidos), "
    "fiel ao teor da intimação e ao tipo de petição indicado. Produza apenas a minuta — ela "
    "será revisada e protocolada por um advogado humano responsável."
)


def draft_peticao(
    *,
    intimacao_texto: str,
    classificacao: ClassificacaoIntimacao,
    contexto_processo: dict,
    client: anthropic.Anthropic | None = None,
    model: str = _MODEL,
) -> str:
    client = client or anthropic.Anthropic()

    contexto = {k: v for k, v in contexto_processo.items() if k in _ALLOWED_CONTEXT_KEYS}
    contexto_linhas = "\n".join(f"- {k}: {v}" for k, v in contexto.items())

    prompt = (
        f"Tipo de petição: {classificacao.peticao_sugerida}\n"
        f"Prazo: {classificacao.prazo_dias} dias "
        f"({'úteis' if classificacao.dias_uteis else 'corridos'})\n"
        f"Dados do processo:\n{contexto_linhas}\n\n"
        f"Teor da intimação:\n{intimacao_texto}\n\n"
        f"Redija a minuta da {classificacao.peticao_sugerida}."
    )

    response = client.messages.create(
        model=model,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")
