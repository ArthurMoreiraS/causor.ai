"""O simulador precisa reproduzir a armadilha real dos portais."""

from app.connectors.simulators import eproc, esaj, pje, projudi

SIMULADORES = (eproc.build(), pje.build(), esaj.build(), projudi.build())


def test_login_tem_campo_de_senha_de_verdade():
    for sim in SIMULADORES:
        assert 'type="password"' in sim.login_html(), sim.sistema


def test_painel_tem_alterar_senha_mas_nao_tem_campo_de_senha():
    """Esta é a armadilha que quebrou handlers.py: a palavra 'senha' aparece
    no painel logado, mas não há formulário de senha."""
    for sim in SIMULADORES:
        panel = sim.panel_html()
        assert "Alterar Senha" in panel, sim.sistema
        assert 'type="password"' not in panel, sim.sistema


def test_painel_tem_marcador_de_autenticado():
    for sim in SIMULADORES:
        assert 'href="#logout"' in sim.panel_html(), sim.sistema


def test_login_nao_tem_marcador_de_autenticado():
    for sim in SIMULADORES:
        assert 'href="#logout"' not in sim.login_html(), sim.sistema


def test_login_contem_a_palavra_processo():
    """O falso positivo do conector PJe: 'processo' na tela de login."""
    for sim in SIMULADORES:
        assert "processo" in sim.login_html().lower(), sim.sistema
