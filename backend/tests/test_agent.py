"""TDD for the agent layer — Claude classification + drafting, with a mocked client.

No real network calls. We assert on how the agent invokes the Anthropic SDK and
how it maps responses, not on Claude's actual output. Crucially, we also assert
that secrets never leak into prompts.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.agent.classifier import ClassificacaoIntimacao, classify_intimacao
from app.agent.drafter import draft_peticao

TEXTO = "Fica a parte ré intimada para apresentar contestação no prazo de 15 dias úteis."


def _fake_classify_client(result: ClassificacaoIntimacao) -> MagicMock:
    client = MagicMock()
    client.messages.parse.return_value = SimpleNamespace(parsed_output=result)
    return client


def _fake_draft_client(text: str) -> MagicMock:
    client = MagicMock()
    block = SimpleNamespace(type="text", text=text)
    client.messages.create.return_value = SimpleNamespace(content=[block])
    return client


def test_classify_returns_structured_result():
    expected = ClassificacaoIntimacao(
        tipo="Intimação para contestar",
        peticao_sugerida="Contestação",
        prazo_dias=15,
        dias_uteis=True,
        confianca=0.92,
        resumo="Réu intimado para contestar em 15 dias úteis.",
    )
    client = _fake_classify_client(expected)

    result = classify_intimacao(TEXTO, client=client)

    assert result == expected
    # Uses Opus 4.8 with adaptive thinking + high effort and structured output.
    kwargs = client.messages.parse.call_args.kwargs
    assert kwargs["model"] == "claude-opus-4-8"
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["output_config"] == {"effort": "high"}
    assert kwargs["output_format"] is ClassificacaoIntimacao


def test_classify_sends_intimacao_text_in_prompt():
    expected = ClassificacaoIntimacao(
        tipo="x", peticao_sugerida="y", prazo_dias=5, dias_uteis=True, confianca=0.5, resumo="z"
    )
    client = _fake_classify_client(expected)
    classify_intimacao(TEXTO, client=client)
    messages = client.messages.parse.call_args.kwargs["messages"]
    assert any(TEXTO in str(m["content"]) for m in messages)


def test_draft_returns_text():
    client = _fake_draft_client("EXCELENTÍSSIMO... CONTESTAÇÃO ...")
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
        client=client,
    )
    assert "CONTESTAÇÃO" in texto
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-opus-4-8"
    assert kwargs["output_config"] == {"effort": "high"}


def test_draft_never_leaks_secrets():
    """A draft prompt must never carry credentials/passwords (vault-only rule)."""
    client = _fake_draft_client("peça")
    classificacao = ClassificacaoIntimacao(
        tipo="t", peticao_sugerida="Contestação", prazo_dias=15, dias_uteis=True,
        confianca=0.9, resumo="r",
    )
    contexto = {"numero": "0001", "senha_certificado": "NUNCA_ENVIAR", "pfx_password": "x"}
    draft_peticao(
        intimacao_texto=TEXTO, classificacao=classificacao, contexto_processo=contexto, client=client
    )
    sent = str(client.messages.create.call_args.kwargs["messages"])
    assert "NUNCA_ENVIAR" not in sent
    assert "senha_certificado" not in sent
    assert "pfx_password" not in sent
