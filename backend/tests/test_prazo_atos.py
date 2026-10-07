"""Catálogo determinístico de prazos por ato e rito."""

import pytest

from app.prazo_engine.atos import ATOS, RITOS, candidatos, sem_prazo


@pytest.mark.parametrize(("ato", "rito", "principal", "dias"), [
    ("sentenca", "comum", "Apelação", 15),
    ("acordao", "comum", "Recurso especial / extraordinário", 15),
    ("decisao_interlocutoria", "comum", "Agravo de instrumento (se cabível no art. 1.015)", 15),
    ("decisao_monocratica_tribunal", "comum", "Agravo interno", 15),
    ("inadmissao_recurso_excepcional", "comum",
     "Agravo em REsp/RE (art. 1.042) ou agravo interno (art. 1.030, § 2º), conforme o fundamento", 15),
    ("intimacao_manifestacao", "comum", "Manifestação (prazo legal supletivo)", 5),
    ("sentenca", "juizado", "Recurso inominado", 10),
    ("sentenca", "trabalhista", "Recurso ordinário", 8),
    ("acordao", "trabalhista", "Recurso de revista", 8),
])
def test_principal_por_ato_e_rito(ato, rito, principal, dias):
    primeiro = candidatos(ato, rito)[0]
    assert (primeiro.ato_cabivel, primeiro.dias) == (principal, dias)
    assert primeiro.fundamento and primeiro.fonte.startswith("https://www.planalto.gov.br/")


def test_decisoes_recorriveis_oferecem_embargos_de_declaracao_em_cinco_dias():
    for ato in ("sentenca", "acordao", "decisao_interlocutoria", "decisao_monocratica_tribunal"):
        nomes = {c.ato_cabivel: c.dias for c in candidatos(ato, "comum")}
        assert nomes["Embargos de declaração"] == 5


@pytest.mark.parametrize("rito", ["criminal", "incerto", "outro"])
def test_rito_sem_regra_segura_nao_sugere_prazo(rito):
    assert all(candidatos(ato, rito) == () for ato in ATOS)


def test_citacao_e_outros_atos_nao_tem_sugestao_automatica():
    assert candidatos("citacao", "comum") == ()
    assert candidatos("outro", "comum") == ()


def test_pauta_e_distribuicao_sao_sem_prazo_explicado():
    assert "pauta" in sem_prazo("pauta_julgamento")
    assert "distribuição" in sem_prazo("distribuicao_ou_expediente")
    assert sem_prazo("sentenca") is None


def test_catalogo_so_usa_atos_e_ritos_conhecidos():
    from app.prazo_engine.atos import _CATALOGO

    assert all(ato in ATOS and rito in RITOS for ato, rito in _CATALOGO)
    assert all(1 <= c.dias <= 30 for regras in _CATALOGO.values() for c in regras)
