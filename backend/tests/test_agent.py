"""TDD for the agent layer — classification + drafting over a pluggable provider.

No real network calls. We inject a fake LLMProvider and assert how the agent
builds the prompt and maps the result, not on any model's actual output.
Crucially, we still assert that secrets never leak into prompts.

Provider-specific SDK wiring is tested in test_llm.py.
"""

from app.agent.classifier import ClassificacaoIntimacao, classify_intimacao
from app.agent.drafter import MinutaGerada, draft_peticao

TEXTO = "Fica a parte ré intimada para apresentar contestação no prazo de 15 dias úteis."

_CLASSIF = ClassificacaoIntimacao(
    tipo="Intimação para contestar",
    peticao_sugerida="Contestação",
    prazo_dias=15,
    dias_uteis=True,
    confianca=0.92,
    resumo="Réu intimado para contestar em 15 dias úteis.",
)

_MINUTA = MinutaGerada(
    contexto_consolidado="Processo distribuído; réu ora intimado para contestar.",
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


def test_draft_returns_structured_minuta():
    provider = _FakeProvider(structured=_MINUTA)

    resultado = draft_peticao(
        intimacao_texto=TEXTO,
        classificacao=_CLASSIF,
        contexto_processo={"numero": "00000010020248260100", "classe": "Procedimento Comum"},
        provider=provider,
    )

    assert isinstance(resultado, MinutaGerada)
    assert "CONTESTAÇÃO" in resultado.minuta
    assert resultado.alertas == ["falta qualificação completa do réu"]
    assert provider.structured_calls[0]["schema"] is MinutaGerada
    assert _CLASSIF.peticao_sugerida in provider.structured_calls[0]["user"]


def test_draft_injects_history_and_ready_deadline_without_recalculating():
    """The drafter must receive the history + the pre-computed deadline, and be told
    explicitly not to recompute it (deterministic-deadline rule)."""
    provider = _FakeProvider(structured=_MINUTA)

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
    provider = _FakeProvider(structured=_MINUTA)

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
    provider = _FakeProvider(structured=_MINUTA)
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
            return _MINUTA

    def fake_get_provider(*, model=None):
        seen["model"] = model
        return Provider()

    monkeypatch.setattr(drafter, "get_provider", fake_get_provider)

    drafter.draft_peticao(
        intimacao_texto="texto",
        classificacao=_CLASSIF,
        contexto_processo={},
    )

    assert seen["model"] == "claude-sonnet-4-6"
