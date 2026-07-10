"""Petition drafting via Claude.

The draft is always a proposal. Filing passes the human-approval gate (see the
API/peticao status flow). This keeps the lawyer professionally responsible.

O modelo NÃO tem ferramentas na redação: todo o contexto (metadados, prazo já
calculado, histórico do processo, template) é pré-montado e injetado como texto.
DataJud/DJEN já foram capturados para o SOR pela camada ``capture/`` — o redator
raciocina sobre esse contexto local, nunca "consulta" sistemas externos.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

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
    "Você é o redator jurídico do Causor. Você recebe um dossiê do processo já montado "
    "pelo sistema — metadados, a classificação da intimação, o prazo JÁ CALCULADO, o "
    "histórico de movimentações/intimações/petições anteriores e o template do "
    "escritório. Trabalhe EXCLUSIVAMENTE com o que foi fornecido no contexto.\n\n"
    "Regras invioláveis:\n"
    "- Não consulte, não busque e não finja acessar DataJud, DJEN, PJe ou qualquer "
    "sistema externo. Todo o contexto necessário já está no prompt; se um dado não está "
    "aqui, ele não existe para você.\n"
    "- NÃO calcule, recalcule nem altere o prazo. A data fatal e a contagem são "
    "determinísticas e vêm prontas; use-as como estão. Nunca invente prazo.\n"
    "- Não invente fatos, partes, decisões, pedidos ou fundamentos ausentes do contexto. "
    "Se faltar informação para redigir com segurança, deixe o campo em destaque "
    "(ex.: [NOME DO CLIENTE]) e registre a lacuna em `alertas`.\n"
    "- Nunca cite o nome de uma autoridade específica (ministro, desembargador, juiz, "
    "relator) a menos que esse nome apareça literalmente no teor da intimação, no "
    "histórico ou nos dados do processo fornecidos. Sem essa citação literal, refira-se "
    "de forma genérica (ex.: \"o relator do processo\", \"o juízo\") e registre a "
    "ausência em `alertas`.\n"
    "- Use o histórico para tornar a minuta aderente ao caso concreto: relacione a "
    "intimação com a última decisão/movimentação e com o que a parte já requereu.\n"
    "- Quando o contexto incluir rótulos de citação no formato [DOC-N p.M], cite o "
    "rótulo correspondente ao afirmar fatos extraídos dos autos (ex.: \"conforme "
    "decisão [DOC-12 p.3]\"). Não invente rótulos que não estejam no contexto.\n"
    "- A minuta é uma proposta, revisada e protocolada por um advogado humano "
    "responsável. Produza a peça, não conselhos ao advogado.\n\n"
    "Redija em português jurídico formal e estruturado (endereçamento, qualificação, "
    "fatos, fundamentos, pedidos), fiel ao teor da intimação e ao tipo de petição, "
    "preservando a estrutura do template quando houver. Devolva os campos: "
    "analise_providencia, minuta e alertas."
)

# Autoridades (ministro/desembargador/juiz/relator) mencionadas no texto gerado que
# nao aparecem literalmente na fonte injetada no prompt. Defesa determinstica contra
# alucinacao de entidades: a instrucao acima ja proibe isso, mas ja observamos o
# modelo citar uma autoridade real inexistente no contexto mesmo assim.
_AUTORIDADE_RE = re.compile(
    r"\b(Ministr[oa]|Desembargador(?:a)?|Ju[ií]z(?:a)?|Relator(?:a)?)\s+"
    r"((?:[A-ZÀ-Ú][\wÀ-ÿ]*\s*){1,4})"
)


def _autoridades_nao_verificadas(texto: str, fonte: str) -> list[str]:
    """Sinaliza mencoes a autoridades no `texto` gerado pelo modelo que nao aparecem
    (literalmente, case-insensitive) na `fonte` que foi realmente injetada no prompt."""
    fonte_normalizada = fonte.lower()
    avisos: list[str] = []
    vistos: set[str] = set()
    for match in _AUTORIDADE_RE.finditer(texto or ""):
        mencao = match.group(0).strip()
        if mencao.lower() in fonte_normalizada or mencao in vistos:
            continue
        vistos.add(mencao)
        avisos.append(
            f'Verificar: "{mencao}" não foi localizado no histórico/teor fornecido ao '
            "redator — confirme antes de usar (possível invenção do modelo)."
        )
    return avisos


def _consolidar_contexto(
    *,
    classificacao: ClassificacaoIntimacao,
    contexto_processo: dict,
    historico: str | None,
    prazo_fatal: str | None,
) -> str:
    """Monta a linha do tempo do processo por código, não pelo modelo.

    Todo dado usado aqui já é determinístico (metadados whitelisted do processo,
    classificação estruturada, histórico montado por `_historico_processo` no SOR,
    prazo já calculado) — não há síntese do LLM nesse campo, então não há como ele
    inventar um nome/entidade aqui (foi exatamente onde a alucinação apareceu antes).
    """
    linhas: list[str] = []

    processo_bits = [f"{k}: {v}" for k, v in contexto_processo.items() if v]
    if processo_bits:
        linhas.append("Processo — " + "; ".join(processo_bits) + ".")

    prazo_txt = f"{classificacao.prazo_dias} dias ({'úteis' if classificacao.dias_uteis else 'corridos'})"
    if prazo_fatal:
        prazo_txt += f", data fatal {prazo_fatal}"
    linhas.append(
        f"Ato: {classificacao.tipo} — petição cabível: {classificacao.peticao_sugerida}. "
        f"Prazo: {prazo_txt}."
    )

    linhas.append(historico or "Sem histórico adicional registrado no sistema.")

    return "\n\n".join(linhas)


class _MinutaRedigida(BaseModel):
    """Schema pedido ao LLM. Sem `contexto_consolidado` de propósito — esse campo é
    montado deterministicamente em `_consolidar_contexto`, nunca pelo modelo."""

    analise_providencia: str = Field(
        description="O que a intimação exige e qual é a resposta processual cabível."
    )
    minuta: str = Field(description="O texto da peça, pronto para revisão humana.")
    alertas: list[str] = Field(
        default_factory=list,
        description="Dados ausentes, inconsistências ou pontos que exigem revisão humana.",
    )
    confianca: float = Field(
        ge=0.0, le=1.0, description="Confiança 0..1 da minuta gerada dado o contexto."
    )


class MinutaGerada(BaseModel):
    """Dossiê consolidado + a minuta. `minuta` vai para `peticao.conteudo`; o restante
    é apoio à decisão do advogado, guardado em `peticao.dossie`."""

    contexto_consolidado: str = Field(
        description=(
            "Linha do tempo objetiva do processo e a relação da intimação atual com o "
            "histórico (última decisão/movimentação, pedidos anteriores)."
        )
    )
    analise_providencia: str = Field(
        description="O que a intimação exige e qual é a resposta processual cabível."
    )
    minuta: str = Field(description="O texto da peça, pronto para revisão humana.")
    alertas: list[str] = Field(
        default_factory=list,
        description="Dados ausentes, inconsistências ou pontos que exigem revisão humana.",
    )
    confianca: float = Field(
        ge=0.0, le=1.0, description="Confiança 0..1 da minuta gerada dado o contexto."
    )


def draft_peticao(
    *,
    intimacao_texto: str,
    classificacao: ClassificacaoIntimacao,
    contexto_processo: dict,
    historico: str | None = None,
    prazo_fatal: str | None = None,
    template_conteudo: str | None = None,
    provider: LLMProvider | None = None,
) -> MinutaGerada:
    provider = provider or get_provider(model=settings.claude_draft_model)

    contexto = {k: v for k, v in contexto_processo.items() if k in _ALLOWED_CONTEXT_KEYS}
    contexto_linhas = (
        "\n".join(f"- {k}: {v}" for k, v in contexto.items()) or "- (sem metadados)"
    )
    historico_bloco = (
        f"[HISTÓRICO DO PROCESSO]\n{historico}\n\n"
        if historico
        else "[HISTÓRICO DO PROCESSO]\n(sem histórico disponível no sistema)\n\n"
    )
    template_bloco = (
        "[TEMPLATE DO ESCRITÓRIO]\nPreserve a estrutura quando aplicável:\n"
        f"{template_conteudo}\n\n"
        if template_conteudo
        else ""
    )
    data_fatal_txt = f" · data fatal: {prazo_fatal}" if prazo_fatal else ""

    prompt = (
        "[CLASSIFICAÇÃO DA INTIMAÇÃO]\n"
        f"Tipo do ato: {classificacao.tipo}\n"
        f"Petição cabível: {classificacao.peticao_sugerida}\n"
        f"Resumo: {classificacao.resumo}\n"
        f"Confiança da classificação: {classificacao.confianca:.2f}\n\n"
        "[PRAZO — JÁ CALCULADO, NÃO ALTERAR]\n"
        f"{classificacao.prazo_dias} dias "
        f"({'úteis' if classificacao.dias_uteis else 'corridos'})"
        f"{data_fatal_txt}\n\n"
        "[DADOS DO PROCESSO]\n"
        f"{contexto_linhas}\n\n"
        f"{historico_bloco}"
        f"{template_bloco}"
        "[TEOR DA INTIMAÇÃO ATUAL]\n"
        f"{intimacao_texto}\n\n"
        f"Tarefa: redija a minuta da {classificacao.peticao_sugerida} aderente ao "
        "momento processual, à luz do contexto acima. Registre em `alertas` qualquer "
        "dado ausente, inconsistência ou ponto que exija revisão humana."
    )

    redigida = provider.complete_structured(
        system=_SYSTEM, user=prompt, schema=_MinutaRedigida, max_tokens=8000
    )

    fonte = "\n".join(str(v) for v in contexto.values())
    fonte += f"\n{historico or ''}\n{intimacao_texto}"
    avisos_autoridade = _autoridades_nao_verificadas(redigida.analise_providencia, fonte)
    avisos_autoridade += _autoridades_nao_verificadas(redigida.minuta, fonte)

    return MinutaGerada(
        contexto_consolidado=_consolidar_contexto(
            classificacao=classificacao,
            contexto_processo=contexto,
            historico=historico,
            prazo_fatal=prazo_fatal,
        ),
        analise_providencia=redigida.analise_providencia,
        minuta=redigida.minuta,
        alertas=list(redigida.alertas) + avisos_autoridade,
        confianca=redigida.confianca,
    )
