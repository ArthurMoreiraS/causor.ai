"""Regra do radar de prazo — uma decisão, dois consumidores.

``GET /alertas`` (o painel) e o notificador que manda o aviso para fora do app
precisam concordar sobre *quais* prazos estão em alerta e em *que* nível. Se
divergirem, o e-mail diz uma coisa e a tela diz outra sobre o mesmo prazo.
"""

from datetime import date

import pytest

from app.alertas.radar import prazos_em_alerta
from app.sor import models

HOJE = date(2026, 7, 30)


@pytest.fixture
def escritorio(db_session):
    esc = models.Escritorio(nome="Escritório Radar")
    db_session.add(esc)
    db_session.flush()
    return esc


def _prazo(db_session, esc, *, data_fatal: date, cumprido: bool = False, descricao="Peça"):
    prazo = models.Prazo(
        escritorio_id=esc.id,
        processo_id=None,
        intimacao_id=None,
        descricao=descricao,
        data_inicio=date(2026, 7, 1),
        dias=15,
        dias_uteis=True,
        data_fatal=data_fatal,
        cumprido=cumprido,
    )
    db_session.add(prazo)
    db_session.flush()
    return prazo


def _niveis(db_session, esc):
    return {
        a.prazo.descricao: a.nivel
        for a in prazos_em_alerta(db_session, escritorio_id=esc.id, hoje=HOJE)
    }


def test_classifica_os_quatro_niveis(db_session, escritorio):
    _prazo(db_session, escritorio, data_fatal=date(2026, 7, 28), descricao="vencido")
    _prazo(db_session, escritorio, data_fatal=HOJE, descricao="hoje")
    _prazo(db_session, escritorio, data_fatal=date(2026, 7, 31), descricao="amanha")
    _prazo(db_session, escritorio, data_fatal=date(2026, 8, 2), descricao="tres_dias")

    assert _niveis(db_session, escritorio) == {
        "vencido": "vencido",
        "hoje": "d0",
        "amanha": "d1",
        "tres_dias": "d3",
    }


def test_prazo_distante_fica_fora_do_radar(db_session, escritorio):
    _prazo(db_session, escritorio, data_fatal=date(2026, 8, 3), descricao="longe")

    assert _niveis(db_session, escritorio) == {}


def test_prazo_cumprido_nao_alerta(db_session, escritorio):
    _prazo(db_session, escritorio, data_fatal=HOJE, cumprido=True, descricao="feito")

    assert _niveis(db_session, escritorio) == {}


def test_ordena_do_mais_critico_para_o_menos(db_session, escritorio):
    _prazo(db_session, escritorio, data_fatal=date(2026, 8, 2), descricao="tres_dias")
    _prazo(db_session, escritorio, data_fatal=date(2026, 7, 28), descricao="vencido")
    _prazo(db_session, escritorio, data_fatal=HOJE, descricao="hoje")

    ordem = [
        a.prazo.descricao
        for a in prazos_em_alerta(db_session, escritorio_id=escritorio.id, hoje=HOJE)
    ]

    assert ordem == ["vencido", "hoje", "tres_dias"]


def test_nao_vaza_prazo_de_outro_escritorio(db_session, escritorio):
    outro = models.Escritorio(nome="Outro")
    db_session.add(outro)
    db_session.flush()
    _prazo(db_session, outro, data_fatal=HOJE, descricao="alheio")

    assert _niveis(db_session, escritorio) == {}


def test_dias_para_vencer_acompanha_o_nivel(db_session, escritorio):
    _prazo(db_session, escritorio, data_fatal=date(2026, 7, 27), descricao="tres_atras")

    alerta = prazos_em_alerta(db_session, escritorio_id=escritorio.id, hoje=HOJE)[0]

    assert alerta.nivel == "vencido"
    assert alerta.dias_para_vencer == -3
