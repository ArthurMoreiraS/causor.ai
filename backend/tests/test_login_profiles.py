"""Detecção de sessão: regras puras e trava de perfil verificado."""

import pytest

from app.connectors.login_profiles import (
    classify_page_state,
    known_login_profiles,
    resolve_login_profile,
)


def test_captcha_tem_precedencia_sobre_tudo():
    assert classify_page_state(authenticated=True, login=True, captcha=True) == "captcha"


def test_formulario_de_login_visivel_significa_ainda_esperando():
    assert classify_page_state(authenticated=False, login=True, captcha=False) == "login"


def test_painel_com_link_alterar_senha_e_autenticado():
    """Regressão do bug de handlers.py: o painel logado tem 'Alterar Senha' no
    menu, mas NÃO tem formulário de senha. Com seletor, login=False."""
    assert classify_page_state(authenticated=True, login=False, captcha=False) == "authenticated"


def test_tela_de_login_com_a_palavra_processo_nao_e_autenticado():
    """Regressão do bug de pje/pages/login.py: 'processo' aparece na tela de
    login de vários tribunais. O que decide é o formulário visível."""
    assert classify_page_state(authenticated=True, login=True, captcha=False) == "login"


def test_nada_reconhecido_e_inconclusivo_nao_erro():
    assert classify_page_state(authenticated=False, login=False, captcha=False) == "inconclusive"


def test_resolve_e_case_insensitive():
    assert resolve_login_profile("eproc") is resolve_login_profile("EPROC")


def test_sistema_desconhecido_nao_tem_perfil():
    assert resolve_login_profile("SISTEMA-QUE-NAO-EXISTE") is None


def test_sistema_vazio_nao_tem_perfil():
    assert resolve_login_profile(None) is None
    assert resolve_login_profile("   ") is None


def test_os_quatro_sistemas_tem_perfil():
    sistemas = {p.sistema for p in known_login_profiles()}
    assert sistemas == {"PJe", "EPROC", "e-SAJ", "Projudi"}


def test_perfil_verificado_exige_evidencia_registrada():
    """Espelha test_todo_perfil_registrado_foi_verificado do MNI. Marcar
    verificado sem ter olhado o portal real é o erro de 2026-07-21."""
    for profile in known_login_profiles():
        if profile.verificado:
            assert profile.evidencia, f"{profile.sistema}: verificado sem evidência"


def test_todo_perfil_tem_seletor_de_login_e_de_autenticado():
    for profile in known_login_profiles():
        assert profile.login_selectors, f"{profile.sistema} sem login_selectors"
        assert profile.authenticated_selectors, f"{profile.sistema} sem authenticated_selectors"


def test_perfil_e_imutavel():
    profile = resolve_login_profile("EPROC")
    with pytest.raises(Exception):
        profile.sistema = "outro"
