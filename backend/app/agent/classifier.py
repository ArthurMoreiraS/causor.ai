"""Intimation classification via Claude (structured output).

Claude *interprets/classifies* the intimation's content — what kind of act it
is, how many days, business vs. calendar. The deadline date math itself stays
in the deterministic prazo_engine; this only produces the inputs to it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.agent.llm import LLMProvider, get_provider
from app.settings import settings

_SYSTEM = (
    "Você é um assistente jurídico especializado em direito processual brasileiro. "
    "Dada uma comunicação/intimação judicial, classifique-a: identifique o tipo de ato, "
    "a petição cabível, o prazo em dias e se a contagem é em dias úteis (CPC art. 219) "
    "ou corridos. Seja conservador na confiança quando o teor for ambíguo. "
    "A contagem da data fatal é feita por outro sistema determinístico — você apenas "
    "interpreta o teor. O prazo_dias deve ser sempre >= 1 (prazo de 0 dias não existe "
    "juridicamente); se o teor não permitir determinar com segurança, use 15 dias como "
    "padrão conservador e baixe a confiança."
)


class ClassificacaoIntimacao(BaseModel):
    tipo: str = Field(description="Tipo do ato (ex.: 'Intimação para contestar').")
    peticao_sugerida: str = Field(description="Petição cabível (ex.: 'Contestação').")
    prazo_dias: int = Field(description="Prazo em dias (sempre >= 1).")
    dias_uteis: bool = Field(description="True se em dias úteis; False se corridos.")
    confianca: float = Field(ge=0.0, le=1.0, description="Confiança 0..1 da classificação.")
    resumo: str = Field(description="Resumo objetivo do que foi intimado.")

    @field_validator("prazo_dias")
    @classmethod
    def _coerce_prazo_minimo(cls, value: int) -> int:
        # Modelos mais fracos (e.g. Llama via Groq) podem devolver 0 quando o
        # teor e ambiguo. Prazo de 0 dias e juridicamente impossivel e faz o
        # motor deterministico (compute_deadline) explodir. Coerce ao minimo
        # legal (1 dia) para o fluxo nao quebrar antes de redigir a minuta; o
        # advogado revisa o prazo calculado de qualquer forma.
        if value < 1:
            return 1
        return value


def classify_intimacao(
    texto: str,
    *,
    provider: LLMProvider | None = None,
) -> ClassificacaoIntimacao:
    provider = provider or get_provider(model=settings.claude_classification_model)
    result = provider.complete_structured(
        system=_SYSTEM,
        user=f"Classifique a seguinte intimação:\n\n{texto}",
        schema=ClassificacaoIntimacao,
    )
    return result
