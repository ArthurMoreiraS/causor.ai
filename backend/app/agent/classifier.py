"""Intimation classification via Claude (structured output).

Claude *interprets/classifies* the intimation's content — what kind of act it
is, how many days, business vs. calendar. The deadline date math itself stays
in the deterministic prazo_engine; this only produces the inputs to it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agent.llm import LLMProvider, get_provider

_SYSTEM = (
    "Você é um assistente jurídico especializado em direito processual brasileiro. "
    "Dada uma comunicação/intimação judicial, classifique-a: identifique o tipo de ato, "
    "a petição cabível, o prazo em dias e se a contagem é em dias úteis (CPC art. 219) "
    "ou corridos. Seja conservador na confiança quando o teor for ambíguo. "
    "A contagem da data fatal é feita por outro sistema determinístico — você apenas "
    "interpreta o teor."
)


class ClassificacaoIntimacao(BaseModel):
    tipo: str = Field(description="Tipo do ato (ex.: 'Intimação para contestar').")
    peticao_sugerida: str = Field(description="Petição cabível (ex.: 'Contestação').")
    prazo_dias: int = Field(description="Prazo em dias.")
    dias_uteis: bool = Field(description="True se em dias úteis; False se corridos.")
    confianca: float = Field(ge=0.0, le=1.0, description="Confiança 0..1 da classificação.")
    resumo: str = Field(description="Resumo objetivo do que foi intimado.")


def classify_intimacao(
    texto: str,
    *,
    provider: LLMProvider | None = None,
) -> ClassificacaoIntimacao:
    provider = provider or get_provider()
    result = provider.complete_structured(
        system=_SYSTEM,
        user=f"Classifique a seguinte intimação:\n\n{texto}",
        schema=ClassificacaoIntimacao,
    )
    return result
