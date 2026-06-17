"""Tests for the agentic chat loop (Claude client mocked)."""

from types import SimpleNamespace

from app.agent import assistant


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_block(name, tool_input, id="tool-1"):
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=id)


class FakeClient:
    """Returns queued responses; records the kwargs it was called with."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=self._responses.pop(0))


def _read_tool(session, name, tool_input):
    return f"RESULT::{name}"


def test_loop_executa_ferramenta_de_leitura_e_responde():
    client = FakeClient(
        [
            [_tool_block("listar_prazos", {})],
            [_text_block("Voce tem 1 prazo pendente.")],
        ]
    )
    result = assistant.chat_with_assistant(
        [{"role": "user", "content": "Quais meus prazos?"}],
        client=client,
        session=object(),
        read_tool_runner=_read_tool,
    )

    assert result["reply"] == "Voce tem 1 prazo pendente."
    assert result["proposed_actions"] == []
    assert {t["ferramenta"] for t in result["tool_trace"]} == {"listar_prazos"}
    assert any("RESULT::listar_prazos" in str(c["messages"]) for c in client.calls)


def test_loop_intercepta_acao_como_proposta_sem_executar():
    client = FakeClient(
        [
            [_tool_block("gerar_minuta", {"intimacao_id": 7})],
            [_text_block("Preparei a proposta de minuta para sua confirmacao.")],
        ]
    )
    result = assistant.chat_with_assistant(
        [{"role": "user", "content": "Gere a minuta da intimacao 7"}],
        client=client,
        session=object(),
        read_tool_runner=_read_tool,
    )

    assert len(result["proposed_actions"]) == 1
    action = result["proposed_actions"][0]
    assert action["tipo"] == "gerar_minuta"
    assert action["endpoint"] == "/intimacoes/7/draft"
    assert "confirmacao" in result["reply"].lower()


def test_loop_passa_ferramentas_e_nunca_inclui_protocolar():
    client = FakeClient([[_text_block("ok")]])
    assistant.chat_with_assistant(
        [{"role": "user", "content": "oi"}],
        client=client,
        session=object(),
        read_tool_runner=_read_tool,
    )

    names = {d["name"] for d in client.calls[0]["tools"]}
    assert "listar_prazos" in names
    assert not any("protocol" in n for n in names)


def test_converte_role_assistant_para_assistant():
    client = FakeClient([[_text_block("ok")]])
    assistant.chat_with_assistant(
        [
            {"role": "user", "content": "oi"},
            {"role": "assistant", "content": "ola, como ajudo?"},
            {"role": "user", "content": "quais meus prazos?"},
        ],
        client=client,
        session=object(),
        read_tool_runner=_read_tool,
    )

    roles = [m["role"] for m in client.calls[0]["messages"]]
    assert roles == ["user", "assistant", "user"]


def test_chat_usa_haiku_por_default():
    client = FakeClient([[_text_block("ok")]])
    assistant.chat_with_assistant(
        [{"role": "user", "content": "oi"}],
        client=client,
        session=object(),
        read_tool_runner=_read_tool,
    )

    assert client.calls[0]["model"] == "claude-haiku-4-5"
