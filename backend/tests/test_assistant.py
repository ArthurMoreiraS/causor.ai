"""Tests for the agentic chat loop (Gemini client mocked).

The assistant runs on Gemini; the drafter/classifier stay on Claude. We mock the
``client.models.generate_content`` surface so the loop is exercised offline.
"""

from types import SimpleNamespace

from app.agent import assistant


def _text_part(t):
    return SimpleNamespace(text=t, function_call=None)


def _call_part(name, args, id="fc1"):
    return SimpleNamespace(text=None, function_call=SimpleNamespace(name=name, args=args, id=id))


def _content(parts):
    return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=parts))])


class FakeClient:
    """Returns queued responses; records the kwargs it was called with."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, **kwargs):
        self.calls.append(kwargs)
        return _content(self._responses.pop(0))


def _read_tool(session, name, tool_input):
    return f"RESULT::{name}"


def test_loop_executa_ferramenta_de_leitura_e_responde():
    client = FakeClient(
        [
            [_call_part("listar_prazos", {})],          # 1ª resposta: pede leitura
            [_text_part("Você tem 1 prazo pendente.")],  # 2ª resposta: texto final
        ]
    )
    result = assistant.chat_with_assistant(
        [{"role": "user", "content": "Quais meus prazos?"}],
        client=client,
        session=object(),
        read_tool_runner=_read_tool,
    )
    assert result["reply"] == "Você tem 1 prazo pendente."
    assert result["proposed_actions"] == []
    assert {t["ferramenta"] for t in result["tool_trace"]} == {"listar_prazos"}
    # a leitura virou function_response na 2ª chamada (contents)
    assert any("RESULT::listar_prazos" in str(c["contents"]) for c in client.calls)


def test_loop_intercepta_acao_como_proposta_sem_executar():
    client = FakeClient(
        [
            [_call_part("gerar_minuta", {"intimacao_id": 7})],
            [_text_part("Preparei a proposta de minuta para sua confirmação.")],
        ]
    )
    result = assistant.chat_with_assistant(
        [{"role": "user", "content": "Gere a minuta da intimação 7"}],
        client=client,
        session=object(),
        read_tool_runner=_read_tool,
    )
    assert len(result["proposed_actions"]) == 1
    action = result["proposed_actions"][0]
    assert action["tipo"] == "gerar_minuta"
    assert action["endpoint"] == "/intimacoes/7/draft"
    assert "confirmação" in result["reply"].lower()


def test_loop_passa_ferramentas_e_nunca_inclui_protocolar():
    client = FakeClient([[_text_part("ok")]])
    assistant.chat_with_assistant(
        [{"role": "user", "content": "oi"}],
        client=client,
        session=object(),
        read_tool_runner=_read_tool,
    )
    decls = client.calls[0]["config"]["tools"][0]["function_declarations"]
    names = {d["name"] for d in decls}
    assert "listar_prazos" in names
    assert not any("protocol" in n for n in names)


def test_converte_role_assistant_para_model():
    client = FakeClient([[_text_part("ok")]])
    assistant.chat_with_assistant(
        [
            {"role": "user", "content": "oi"},
            {"role": "assistant", "content": "olá, como ajudo?"},
            {"role": "user", "content": "quais meus prazos?"},
        ],
        client=client,
        session=object(),
        read_tool_runner=_read_tool,
    )
    contents = client.calls[0]["contents"]
    roles = [c["role"] for c in contents]
    assert roles == ["user", "model", "user"]
