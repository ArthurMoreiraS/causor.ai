"""TDD for the agent layer — classification + drafting over a pluggable provider.

No real network calls. We inject a fake LLMProvider and assert how the agent
builds the prompt and maps the result, not on any model's actual output.
Crucially, we still assert that secrets never leak into prompts.

Provider-specific SDK wiring is tested in test_llm.py.
"""

from app.agent.classifier import ClassificacaoIntimacao, classify_intimacao
from app.agent.drafter import MinutaGerada, _MinutaRedigida, draft_peticao

TEXTO = "Fica a parte ré intimada para apresentar contestação no prazo de 15 dias úteis."

_CLASSIF = ClassificacaoIntimacao(
    tipo="Intimação para contestar",
    peticao_sugerida="Contestação",
    prazo_dias=15,
    dias_uteis=True,
    confianca=0.92,
    resumo="Réu intimado para contestar em 15 dias úteis.",
)

# O que o LLM realmente devolve — sem contexto_consolidado, que agora e montado
# deterministicamente por codigo (ver test_agent.py::test_draft_* abaixo).
_MINUTA_LLM = _MinutaRedigida(
    analise_providencia="Cabe apresentar contestação no prazo legal.",
    minuta="EXCELENTÍSSIMO... CONTESTAÇÃO ...",
    alertas=["falta qualificação completa do réu"],
    confianca=0.8,
)


class _FakeProvider:
    """Records the system/user/schema it receives and returns canned output."""

    def __init__(self, *, structured=None, text: str = "") -> None:
        self._structured = structured
        self._text = text
        self.structured_calls: list[dict] = []
        self.text_calls: list[dict] = []

    def complete_structured(self, *, system, user, schema, max_tokens=None):
        self.structured_calls.append(
            {"system": system, "user": user, "schema": schema, "max_tokens": max_tokens}
        )
        return self._structured

    def complete_text(self, *, system, user, max_tokens):
        self.text_calls.append({"system": system, "user": user, "max_tokens": max_tokens})
        return self._text


def test_classify_returns_structured_result():
    expected = ClassificacaoIntimacao(
        tipo="Intimação para contestar",
        peticao_sugerida="Contestação",
        prazo_dias=15,
        dias_uteis=True,
        confianca=0.92,
        resumo="Réu intimado para contestar em 15 dias úteis.",
    )
    provider = _FakeProvider(structured=expected)

    result = classify_intimacao(TEXTO, provider=provider)

    assert result == expected
    assert provider.structured_calls[0]["schema"] is ClassificacaoIntimacao


def test_classify_sends_intimacao_text_in_prompt():
    expected = ClassificacaoIntimacao(
        tipo="x", peticao_sugerida="y", prazo_dias=5, dias_uteis=True, confianca=0.5, resumo="z"
    )
    provider = _FakeProvider(structured=expected)

    classify_intimacao(TEXTO, provider=provider)

    assert TEXTO in provider.structured_calls[0]["user"]


def test_classify_coerces_zero_prazo_to_minimum():
    """Modelos fracos (Llama/Groq) podem devolver prazo_dias=0; o motor
    deterministico rejeita <1. O schema coerciona para 1 na validacao, entao
    qualquer provider (Claude parse ou OpenAI-compat model_validate) produzia
    prazo valido e o fluxo nao quebra antes de redigir a minuta."""
    coerced = ClassificacaoIntimacao(
        tipo="x", peticao_sugerida="y", prazo_dias=0, dias_uteis=True,
        confianca=0.2, resumo="z",
    )
    assert coerced.prazo_dias == 1

    negative = ClassificacaoIntimacao(
        tipo="x", peticao_sugerida="y", prazo_dias=-3, dias_uteis=False,
        confianca=0.1, resumo="z",
    )
    assert negative.prazo_dias == 1


def test_draft_returns_structured_minuta():
    provider = _FakeProvider(structured=_MINUTA_LLM)

    resultado = draft_peticao(
        intimacao_texto=TEXTO,
        classificacao=_CLASSIF,
        contexto_processo={"numero": "00000010020248260100", "classe": "Procedimento Comum"},
        provider=provider,
    )

    assert isinstance(resultado, MinutaGerada)
    assert "CONTESTAÇÃO" in resultado.minuta
    assert resultado.alertas == ["falta qualificação completa do réu"]
    assert provider.structured_calls[0]["schema"] is _MinutaRedigida
    assert _CLASSIF.peticao_sugerida in provider.structured_calls[0]["user"]


def test_draft_consolidates_context_deterministically_not_via_llm():
    """contexto_consolidado nunca deve vir do LLM — sempre montado por codigo a
    partir de dados ja deterministicos (classificacao, metadados, historico).
    Isso evita a alucinacao de nomes/autoridades observada em producao."""
    provider = _FakeProvider(structured=_MINUTA_LLM)

    resultado = draft_peticao(
        intimacao_texto=TEXTO,
        classificacao=_CLASSIF,
        contexto_processo={"numero": "00000010020248260100", "classe": "Procedimento Comum"},
        historico="Intimações anteriores:\n- 2026-05-06 · Comunicação: teor anterior",
        prazo_fatal="2026-07-23",
        provider=provider,
    )

    assert "Procedimento Comum" in resultado.contexto_consolidado
    assert _CLASSIF.tipo in resultado.contexto_consolidado
    assert "2026-07-23" in resultado.contexto_consolidado
    assert "teor anterior" in resultado.contexto_consolidado
    # o LLM (schema _MinutaRedigida) nunca teve esse campo para preencher
    assert "contexto_consolidado" not in _MinutaRedigida.model_fields


def test_draft_flags_authority_names_not_present_in_source():
    """Se o LLM citar uma autoridade (ministro/juiz/relator) que nao aparece no
    teor/historico injetado, isso deve virar um alerta automatico."""
    redigida_com_invencao = _MinutaRedigida(
        analise_providencia="O relator, Ministro Sérgio Kukina, já decidiu os embargos.",
        minuta="EXCELENTÍSSIMO... CONTESTAÇÃO ...",
        alertas=[],
        confianca=0.6,
    )
    provider = _FakeProvider(structured=redigida_com_invencao)

    resultado = draft_peticao(
        intimacao_texto="RELATOR: MINISTRO PRESIDENTE DO STJ. Fica intimada a parte.",
        classificacao=_CLASSIF,
        contexto_processo={"numero": "0001"},
        provider=provider,
    )

    assert any("Ministro Sérgio Kukina" in aviso for aviso in resultado.alertas)


def test_draft_does_not_flag_authority_names_present_in_source():
    """Nome de autoridade que aparece de fato no teor/historico nao deve gerar
    alerta — o objetivo e pegar invencao, nao autoridade legitima."""
    redigida_legitima = _MinutaRedigida(
        analise_providencia="O relator, Ministro Sérgio Kukina, ainda não decidiu.",
        minuta="EXCELENTÍSSIMO... CONTESTAÇÃO ...",
        alertas=[],
        confianca=0.8,
    )
    provider = _FakeProvider(structured=redigida_legitima)

    resultado = draft_peticao(
        intimacao_texto="RELATOR: MINISTRO SÉRGIO KUKINA. Fica intimada a parte.",
        classificacao=_CLASSIF,
        contexto_processo={"numero": "0001"},
        provider=provider,
    )

    assert resultado.alertas == []


def test_draft_injects_history_and_ready_deadline_without_recalculating():
    """The drafter must receive the history + the pre-computed deadline, and be told
    explicitly not to recompute it (deterministic-deadline rule)."""
    provider = _FakeProvider(structured=_MINUTA_LLM)

    draft_peticao(
        intimacao_texto=TEXTO,
        classificacao=_CLASSIF,
        contexto_processo={"numero": "0001"},
        historico="Movimentações (mais recentes primeiro):\n- 2024-09-01: Sentença publicada",
        prazo_fatal="2024-09-30",
        provider=provider,
    )

    sent = provider.structured_calls[0]["user"]
    assert "Sentença publicada" in sent  # histórico injetado no contexto
    assert "2024-09-30" in sent  # prazo já calculado, injetado pronto
    assert "NÃO ALTERAR" in sent  # instrução de não recalcular o prazo


def test_draft_without_history_still_drafts():
    provider = _FakeProvider(structured=_MINUTA_LLM)

    resultado = draft_peticao(
        intimacao_texto=TEXTO,
        classificacao=_CLASSIF,
        contexto_processo={"numero": "0001"},
        provider=provider,
    )

    assert isinstance(resultado, MinutaGerada)
    assert "sem histórico disponível" in provider.structured_calls[0]["user"]


def test_draft_never_leaks_secrets():
    """A draft prompt must never carry credentials/passwords (vault-only rule)."""
    provider = _FakeProvider(structured=_MINUTA_LLM)
    contexto = {"numero": "0001", "senha_certificado": "NUNCA_ENVIAR", "pfx_password": "x"}

    draft_peticao(
        intimacao_texto=TEXTO,
        classificacao=_CLASSIF,
        contexto_processo=contexto,
        provider=provider,
    )

    sent = provider.structured_calls[0]["user"]
    assert "NUNCA_ENVIAR" not in sent
    assert "senha_certificado" not in sent
    assert "pfx_password" not in sent


def test_classificacao_usa_haiku_por_padrao(monkeypatch):
    from app.agent import classifier

    seen = {}

    class Provider:
        def complete_structured(self, *, system, user, schema, max_tokens=None):
            return ClassificacaoIntimacao(
                tipo="Intimacao",
                peticao_sugerida="Manifestacao",
                prazo_dias=5,
                dias_uteis=True,
                confianca=0.8,
                resumo="Resumo",
            )

    def fake_get_provider(*, model=None):
        seen["model"] = model
        return Provider()

    monkeypatch.setattr(classifier, "get_provider", fake_get_provider)

    classifier.classify_intimacao("texto")

    assert seen["model"] == "claude-haiku-4-5"


def test_minuta_usa_sonnet_por_padrao(monkeypatch):
    from app.agent import drafter

    seen = {}

    class Provider:
        def complete_structured(self, *, system, user, schema, max_tokens=None):
            return _MINUTA_LLM

    def fake_get_provider(*, model=None):
        seen["model"] = model
        return Provider()

    monkeypatch.setattr(drafter, "get_provider", fake_get_provider)

    drafter.draft_peticao(
        intimacao_texto="texto",
        classificacao=_CLASSIF,
        contexto_processo={},
    )

    assert seen["model"] == "claude-sonnet-5"
