"""O conector PJe usa a mesma fonte de detecção do agente."""

import pytest

from app.connectors.pje.pages.errors import CaptchaDetectedError, PjeSessionInvalidError
from app.connectors.pje.pages.login import LoginPage


class FakeLocator:
    def __init__(self, visible: bool):
        self._visible = visible

    @property
    def first(self):
        return self

    def is_visible(self, timeout: float = 0) -> bool:
        return self._visible


class FakePage:
    def __init__(self, visiveis: set[str]):
        self.visiveis = visiveis

    def locator(self, selector: str):
        return FakeLocator(selector in self.visiveis)


def test_tela_de_login_com_a_palavra_processo_e_sessao_invalida():
    """Regressão: 'processo' era marcador de autenticado, então a tela de
    login passava como sessão válida."""
    page = FakePage({"input[type='password']"})
    with pytest.raises(PjeSessionInvalidError):
        LoginPage(page).ensure_session_valid()


def test_painel_autenticado_passa():
    page = FakePage({"a[href*='logout']"})
    LoginPage(page).ensure_session_valid()  # não levanta


def test_captcha_levanta_erro_proprio():
    page = FakePage({".g-recaptcha"})
    with pytest.raises(CaptchaDetectedError):
        LoginPage(page).ensure_session_valid()


def test_inconclusivo_nao_derruba_o_fluxo():
    """Sem evidência nenhuma, não dá para afirmar que a sessão morreu."""
    LoginPage(FakePage(set())).ensure_session_valid()  # não levanta


def test_modulo_nao_tem_mais_marcadores_proprios():
    from app.connectors.pje.pages import login as login_module

    with open(login_module.__file__, encoding="utf-8") as arquivo:
        conteudo = arquivo.read()
    assert "entrar com gov.br" not in conteudo.lower(), "marcador duplicado voltou"
    assert "authenticated_markers" not in conteudo, "marcador duplicado voltou"
