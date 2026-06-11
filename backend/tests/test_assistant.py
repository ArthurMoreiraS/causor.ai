"""Tests for the agentic chat loop (Anthropic client mocked)."""

from types import SimpleNamespace

from app.agent import assistant


class _Block:
    def __init__(self, type, **kw):
        self.type = type
        for k, v in kw.items():
            setattr(self, k, v)


def _text(t):
    return _Block("text", text=t)


def _tool_use(name, tool_input, id="tu1"):
    return _Block("tool_use", name=name, input=tool_input, id=id)


class FakeClient:
    """Returns queued responses; records the messages it was called with."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        content = self._responses.pop(0)
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        return SimpleNamespace(content=content, stop_reason=stop)


def _read_tool(session, name, tool_input):
    return f"RESULT::{name}"


def test_loop_executa_ferramenta_de_leitura_e_responde():
    client = FakeClient(
        [
            [_tool_use("listar_prazos", {})],          # 1ª resposta: pede leitura
            [_text("Você tem 1 prazo pendente.")],     # 2ª resposta: texto final
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
    # a leitura virou tool_result na 2ª chamada
    assert any("RESULT::listar_prazos" in str(c["messages"]) for c in client.calls)


def test_loop_intercepta_acao_como_proposta_sem_executar():
    client = FakeClient(
        [
            [_tool_use("gerar_minuta", {"intimacao_id": 7})],
            [_text("Preparei a proposta de minuta para sua confirmação.")],
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
    client = FakeClient([[_text("ok")]])
    assistant.chat_with_assistant(
        [{"role": "user", "content": "oi"}],
        client=client,
        session=object(),
        read_tool_runner=_read_tool,
    )
    tools = client.calls[0]["tools"]
    names = {t["name"] for t in tools}
    assert "listar_prazos" in names
    assert not any("protocol" in n for n in names)
