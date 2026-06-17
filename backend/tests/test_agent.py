"""TDD for the agent layer — classification + drafting over a pluggable provider.

No real network calls. We inject a fake LLMProvider and assert how the agent
builds the prompt and maps the result, not on any model's actual output.
Crucially, we still assert that secrets never leak into prompts.

Provider-specific SDK wiring is tested in test_llm.py.
"""

from app.agent.classifier import ClassificacaoIntimacao, classify_intimacao
from app.agent.drafter import draft_peticao

TEXTO = "Fica a parte ré intimada para apresentar contestação no prazo de 15 dias úteis."


class _FakeProvider:
    """Records the system/user/schema it receives and returns canned output."""

    def __init__(self, *, structured=None, text: str = "") -> None:
        self._structured = structured
        self._text = text
        self.structured_calls: list[dict] = []
        self.text_calls: list[dict] = []

    def complete_structured(self, *, system, user, schema):
        self.structured_calls.append({"system": system, "user": user, "schema": schema})
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


def test_draft_returns_text():
    provider = _FakeProvider(text="EXCELENTÍSSIMO... CONTESTAÇÃO ...")
    classificacao = ClassificacaoIntimacao(
        tipo="Intimação para contestar",
        peticao_sugerida="Contestação",
        prazo_dias=15,
        dias_uteis=True,
        confianca=0.92,
        resumo="...",
    )

    texto = draft_peticao(
        intimacao_texto=TEXTO,
        classificacao=classificacao,
        contexto_processo={"numero": "00000010020248260100", "classe": "Procedimento Comum"},
        provider=provider,
    )

    assert "CONTESTAÇÃO" in texto
    assert classificacao.peticao_sugerida in provider.text_calls[0]["user"]


def test_draft_never_leaks_secrets():
    """A draft prompt must never carry credentials/passwords (vault-only rule)."""
    provider = _FakeProvider(text="peça")
    classificacao = ClassificacaoIntimacao(
        tipo="t", peticao_sugerida="Contestação", prazo_dias=15, dias_uteis=True,
        confianca=0.9, resumo="r",
    )
    contexto = {"numero": "0001", "senha_certificado": "NUNCA_ENVIAR", "pfx_password": "x"}

    draft_peticao(
        intimacao_texto=TEXTO,
        classificacao=classificacao,
        contexto_processo=contexto,
        provider=provider,
    )

    sent = provider.text_calls[0]["user"]
    assert "NUNCA_ENVIAR" not in sent
    assert "senha_certificado" not in sent
    assert "pfx_password" not in sent


def test_classificacao_usa_haiku_por_padrao(monkeypatch):
    from app.agent import classifier

    seen = {}

    class Provider:
        def complete_structured(self, *, system, user, schema):
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
        def complete_text(self, *, system, user, max_tokens):
            return "minuta"

    def fake_get_provider(*, model=None):
        seen["model"] = model
        return Provider()

    monkeypatch.setattr(drafter, "get_provider", fake_get_provider)
    classificacao = ClassificacaoIntimacao(
        tipo="Intimacao",
        peticao_sugerida="Manifestacao",
        prazo_dias=5,
        dias_uteis=True,
        confianca=0.8,
        resumo="Resumo",
    )

    drafter.draft_peticao(
        intimacao_texto="texto",
        classificacao=classificacao,
        contexto_processo={},
    )

    assert seen["model"] == "claude-sonnet-4-6"
