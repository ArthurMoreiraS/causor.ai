"""TDD for the persisted agent workflow."""

from datetime import date
from unittest.mock import patch

from app.agent.classifier import ClassificacaoIntimacao
from app.agent.service import draft_from_intimacao
from app.prazo_engine.factory import build_calendar
from app.sor import models


def test_draft_from_intimacao_persists_prazo_and_peticao(db_session):
    esc = models.Escritorio(nome="Escritorio Teste")
    db_session.add(esc)
    db_session.flush()
    proc = models.Processo(escritorio_id=esc.id, numero="00000010020248260100", tribunal="TJSP")
    db_session.add(proc)
    db_session.flush()
    intimacao = models.Intimacao(
        processo_id=proc.id,
        fonte="DJEN",
        fonte_id="111",
        numero_processo=proc.numero,
        tipo_comunicacao="Intimacao",
        teor="Apresente contestacao em 15 dias uteis.",
        data_publicacao=date(2024, 9, 9),
    )
    db_session.add(intimacao)
    db_session.flush()

    classificacao = ClassificacaoIntimacao(
        tipo="Intimacao para contestar",
        peticao_sugerida="Contestacao",
        prazo_dias=15,
        dias_uteis=True,
        confianca=0.93,
        resumo="Reu intimado para contestar.",
    )

    with (
        patch("app.agent.service.classify_intimacao", return_value=classificacao),
        patch("app.agent.service.draft_peticao", return_value="MINUTA"),
    ):
        prazo, peticao, result = draft_from_intimacao(
            db_session, intimacao, calendar=build_calendar([2024, 2025])
        )

    assert result == classificacao
    assert prazo.dias == 15
    assert prazo.descricao == "Intimacao para contestar"
    assert peticao.status == "rascunho"
    assert peticao.tipo == "Contestacao"
    assert peticao.conteudo == "MINUTA"
    assert peticao.processo_id == proc.id
