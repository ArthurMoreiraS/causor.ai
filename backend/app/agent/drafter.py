"""Petition drafting via Claude.

The draft is always a proposal. Filing passes the human-approval gate (see the
API/peticao status flow). This keeps the lawyer professionally responsible.
"""

from __future__ import annotations

from app.agent.classifier import ClassificacaoIntimacao
from app.agent.llm import LLMProvider, get_provider
from app.settings import settings

# Only non-sensitive process metadata may reach the prompt. Secrets
# (certificate passwords, signing credentials) live in the vault and must never
# enter a prompt or log, so we whitelist allowed keys rather than dump a dict.
_ALLOWED_CONTEXT_KEYS = frozenset(
    {"numero", "classe", "tribunal", "orgao_julgador", "comarca", "vara", "cliente", "polo"}
)

_SYSTEM = (
    "Voce e um advogado brasileiro redigindo uma minuta de peticao. Redija em portugues "
    "juridico formal, estruturada (enderecamento, qualificacao, fatos, fundamentos, pedidos), "
    "fiel ao teor da intimacao e ao tipo de peticao indicado. Produza apenas a minuta. Ela "
    "sera revisada e protocolada por um advogado humano responsavel."
)


def draft_peticao(
    *,
    intimacao_texto: str,
    classificacao: ClassificacaoIntimacao,
    contexto_processo: dict,
    template_conteudo: str | None = None,
    provider: LLMProvider | None = None,
) -> str:
    provider = provider or get_provider(model=settings.claude_draft_model)

    contexto = {k: v for k, v in contexto_processo.items() if k in _ALLOWED_CONTEXT_KEYS}
    contexto_linhas = "\n".join(f"- {k}: {v}" for k, v in contexto.items())
    template_bloco = (
        "Template do escritorio a seguir, preserve sua estrutura quando aplicavel:\n"
        f"{template_conteudo}\n\n"
        if template_conteudo
        else ""
    )

    prompt = (
        f"Tipo de peticao: {classificacao.peticao_sugerida}\n"
        f"Prazo: {classificacao.prazo_dias} dias "
        f"({'uteis' if classificacao.dias_uteis else 'corridos'})\n"
        f"Dados do processo:\n{contexto_linhas}\n\n"
        f"{template_bloco}"
        f"Teor da intimacao:\n{intimacao_texto}\n\n"
        f"Redija a minuta da {classificacao.peticao_sugerida}."
    )

    return provider.complete_text(system=_SYSTEM, user=prompt, max_tokens=8000)
