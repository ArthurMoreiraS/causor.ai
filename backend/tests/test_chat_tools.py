"""Tests for the chat agent tool registry."""

from datetime import date

import pytest

from app.agent import chat_tools
from app.sor import models


@pytest.fixture
def seeded(db_session):
    esc = models.Escritorio(nome="Escritorio Teste")
    db_session.add(esc)
    db_session.flush()
    proc = models.Processo(escritorio_id=esc.id, numero="1009988-77.2026.8.26.0100", sistema="e-SAJ")
    db_session.add(proc)
    db_session.flush()
    intim = models.Intimacao(
        processo_id=proc.id, fonte="DJEN", fonte_id="x1",
        numero_processo=proc.numero, tipo_comunicacao="Intimacao para replica",
        teor="Apresente replica em 15 dias.", data_disponibilizacao=date(2026, 6, 1),
    )
    db_session.add(intim)
    db_session.flush()
    prazo = models.Prazo(
        processo_id=proc.id, intimacao_id=intim.id, descricao="Replica",
        data_inicio=date(2026, 6, 2), dias=15, dias_uteis=True,
        data_fatal=date(2026, 6, 23), cumprido=False,
    )
    db_session.add(prazo)
    db_session.flush()
    return {"processo": proc, "intimacao": intim, "prazo": prazo}


def test_tool_definitions_expoem_leitura_e_abertura_de_trabalho_sem_atalho_de_minuta_ou_protocolo():
    names = {t["name"] for t in chat_tools.TOOL_DEFINITIONS}
    assert {"listar_prazos", "buscar_processo", "ler_intimacao"} <= names
    assert "abrir_trabalho" in names
    assert not {"gerar_minuta", "marcar_prazo_cumprido", "aprovar_peticao", "consultar_envio"} & names
    assert not any("protocol" in n for n in names)


def test_acao_e_leitura_estao_corretamente_classificadas():
    assert chat_tools.is_action_tool("abrir_trabalho")
    assert not chat_tools.is_action_tool("gerar_minuta")
    assert not chat_tools.is_action_tool("aprovar_peticao")
    assert not chat_tools.is_action_tool("listar_prazos")


def test_executar_ferramenta_leitura_listar_prazos(db_session, seeded):
    out = chat_tools.execute_read_tool(db_session, "listar_prazos", {})
    assert "Replica" in out
    assert "2026-06-23" in out


def test_executar_ferramenta_leitura_ler_intimacao_filtra_segredos(db_session, seeded):
    out = chat_tools.execute_read_tool(
        db_session, "ler_intimacao", {"intimacao_id": seeded["intimacao"].id}
    )
    assert "replica" in out.lower()
    assert seeded["processo"].numero in out


def test_acao_proposta_constroi_endpoint_e_payload():
    action = chat_tools.build_proposed_action(
        "abrir_trabalho", {"trabalho_id": 7}
    )
    assert action["endpoint"] == "/trabalhos/7"
    assert action["tipo"] == "abrir_trabalho"
    assert action["metodo"] == "GET"


def test_scoped_tools_never_return_another_offices_process_or_work(db_session, seeded):
    from app.auth.jwt_auth import CurrentUser
    office = models.Escritorio(nome="Outro escritório")
    db_session.add(office)
    db_session.flush()
    other = models.Processo(escritorio_id=office.id, numero="77777770020268260100")
    db_session.add(other)
    db_session.flush()
    secret_work = models.TrabalhoJuridico(escritorio_id=office.id, processo_id=other.id, providencia="CONTEUDO-RESTRITO")
    db_session.add(secret_work)
    db_session.flush()
    current = CurrentUser(usuario_id=1, escritorio_id=seeded["processo"].escritorio_id, email="test@example.invalid")
    for tool, args in (("buscar_processo", {"processo_id": other.id}),
                       ("buscar_processo", {"numero": other.numero}),
                       ("consultar_trabalho", {"trabalho_id": secret_work.id}),
                       ("consultar_envio", {"trabalho_id": secret_work.id})):
        result = chat_tools.execute_scoped_read_tool(db_session, tool, args, current=current)
        assert "erro" in result and other.numero not in result and "CONTEUDO-RESTRITO" not in result
