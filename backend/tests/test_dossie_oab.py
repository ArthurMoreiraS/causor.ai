"""Dossiê de uma OAB — o quadro real da carteira, sem pedir credencial.

O nível de alerta tem que sair da mesma função que o painel e o e-mail usam;
uma segunda regra faria o dossiê discordar da tela sobre o mesmo prazo.
"""

from datetime import date

import pytest

from app.relatorios.dossie_oab import montar_dossie, renderizar_markdown
from app.sor import models

HOJE = date(2026, 8, 4)


@pytest.fixture
def escritorio(db_session):
    esc = models.Escritorio(nome="Escritório Dossiê")
    db_session.add(esc)
    db_session.flush()
    return esc


def _intimacao_com_prazo(
    db_session,
    escritorio,
    *,
    fonte_id: str,
    publicacao: date,
    data_fatal: date | None,
    cumprido: bool = False,
):
    processo = models.Processo(
        escritorio_id=escritorio.id,
        numero=f"0000{fonte_id}-11.2026.8.27.2729",
        tribunal="TJTO",
        sistema="EPROC",
    )
    db_session.add(processo)
    db_session.flush()
    intimacao = models.Intimacao(
        processo_id=processo.id,
        escritorio_id=escritorio.id,
        fonte="DJEN",
        fonte_id=fonte_id,
        numero_processo=processo.numero,
        tribunal="TJTO",
        tipo_comunicacao="Intimação",
        data_publicacao=publicacao,
    )
    db_session.add(intimacao)
    db_session.flush()
    if data_fatal is not None:
        db_session.add(
            models.Prazo(
                processo_id=processo.id,
                intimacao_id=intimacao.id,
                escritorio_id=escritorio.id,
                descricao="Manifestação",
                data_inicio=publicacao,
                dias=15,
                dias_uteis=True,
                data_fatal=data_fatal,
                cumprido=cumprido,
            )
        )
        db_session.flush()
    return intimacao


def test_dossie_traz_prazo_calculado_e_nivel_do_radar(db_session, escritorio):
    _intimacao_com_prazo(
        db_session,
        escritorio,
        fonte_id="1",
        publicacao=date(2026, 8, 3),
        data_fatal=date(2026, 8, 5),
    )

    dossie = montar_dossie(
        db_session, escritorio_id=escritorio.id, oab="12345", uf="TO", hoje=HOJE
    )

    assert dossie.total_intimacoes == 1
    assert dossie.total_com_prazo == 1
    assert dossie.total_em_alerta == 1
    linha = dossie.linhas[0]
    assert linha.data_fatal == date(2026, 8, 5)
    assert linha.dias_para_vencer == 1
    assert linha.nivel == "d1"


def test_dossie_ignora_intimacao_fora_da_janela(db_session, escritorio):
    _intimacao_com_prazo(
        db_session,
        escritorio,
        fonte_id="2",
        publicacao=date(2026, 6, 1),
        data_fatal=date(2026, 6, 20),
    )

    dossie = montar_dossie(
        db_session,
        escritorio_id=escritorio.id,
        oab="12345",
        uf="TO",
        hoje=HOJE,
        janela_dias=15,
    )

    assert dossie.total_intimacoes == 0
    assert dossie.linhas == []


def test_dossie_lista_intimacao_sem_prazo_sem_marcar_alerta(db_session, escritorio):
    _intimacao_com_prazo(
        db_session,
        escritorio,
        fonte_id="3",
        publicacao=date(2026, 8, 1),
        data_fatal=None,
    )

    dossie = montar_dossie(
        db_session, escritorio_id=escritorio.id, oab="12345", uf="TO", hoje=HOJE
    )

    assert dossie.total_intimacoes == 1
    assert dossie.total_com_prazo == 0
    assert dossie.total_em_alerta == 0
    assert dossie.linhas[0].nivel is None


def test_dossie_ordena_do_prazo_mais_urgente_para_o_menos(db_session, escritorio):
    _intimacao_com_prazo(
        db_session,
        escritorio,
        fonte_id="4",
        publicacao=date(2026, 8, 1),
        data_fatal=date(2026, 8, 20),
    )
    _intimacao_com_prazo(
        db_session,
        escritorio,
        fonte_id="5",
        publicacao=date(2026, 8, 2),
        data_fatal=date(2026, 8, 6),
    )

    dossie = montar_dossie(
        db_session, escritorio_id=escritorio.id, oab="12345", uf="TO", hoje=HOJE
    )

    assert [linha.data_fatal for linha in dossie.linhas] == [
        date(2026, 8, 6),
        date(2026, 8, 20),
    ]


def test_markdown_tem_cabecalho_numeros_e_a_linha(db_session, escritorio):
    intimacao = _intimacao_com_prazo(
        db_session,
        escritorio,
        fonte_id="6",
        publicacao=date(2026, 8, 3),
        data_fatal=date(2026, 8, 5),
    )

    texto = renderizar_markdown(
        montar_dossie(
            db_session, escritorio_id=escritorio.id, oab="12345", uf="TO", hoje=HOJE
        )
    )

    assert "12345/TO" in texto
    assert intimacao.numero_processo in texto
    assert "2026-08-05" in texto
    # A frase que separa o Causor de "mais uma IA que escreve petição".
    assert "determinístico" in texto


def test_cli_dossie_oab_grava_arquivo(db_session, escritorio, monkeypatch, tmp_path):
    import app.cli as cli

    _intimacao_com_prazo(
        db_session,
        escritorio,
        fonte_id="7",
        publicacao=date(2026, 8, 3),
        data_fatal=date(2026, 8, 5),
    )
    monkeypatch.setattr(cli, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    saida = tmp_path / "dossie.md"

    rc = cli.main(
        [
            "dossie-oab",
            "--escritorio",
            str(escritorio.id),
            "--oab",
            "12345",
            "--uf",
            "to",
            "--hoje",
            "2026-08-04",
            "--saida",
            str(saida),
        ]
    )

    assert rc == 0
    assert "12345/TO" in saida.read_text(encoding="utf-8")
