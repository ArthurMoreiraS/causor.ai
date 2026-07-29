"""Detecção contra uma página falsa que imita a API do Playwright."""

from app.connectors.login_profiles import detect_page_state, resolve_login_profile


class FakeLocator:
    def __init__(self, visible: bool, raises: bool = False):
        self._visible = visible
        self._raises = raises

    @property
    def first(self):
        return self

    def is_visible(self, timeout: float = 0) -> bool:
        if self._raises:
            raise RuntimeError("seletor invalido")
        return self._visible


class FakePage:
    """Devolve visível apenas para os seletores listados."""

    def __init__(self, visiveis: set[str], quebrados: set[str] | None = None):
        self.visiveis = visiveis
        self.quebrados = quebrados or set()

    def locator(self, selector: str):
        if selector in self.quebrados:
            return FakeLocator(False, raises=True)
        return FakeLocator(selector in self.visiveis)


def test_painel_autenticado_com_alterar_senha_e_reconhecido():
    profile = resolve_login_profile("EPROC")
    page = FakePage({"#infraBarraSuperior"})
    assert detect_page_state(page, profile) == "authenticated"


def test_tela_de_login_e_reconhecida_pelo_campo_de_senha():
    profile = resolve_login_profile("EPROC")
    page = FakePage({"input[type='password']"})
    assert detect_page_state(page, profile) == "login"


def test_captcha_vence():
    profile = resolve_login_profile("PJe")
    page = FakePage({".g-recaptcha", "input[type='password']"})
    assert detect_page_state(page, profile) == "captcha"


def test_pagina_desconhecida_e_inconclusiva():
    profile = resolve_login_profile("PJe")
    assert detect_page_state(FakePage(set()), profile) == "inconclusive"


def test_seletor_que_explode_nao_derruba_a_deteccao():
    """Portal muda e um seletor vira inválido: vira inconclusivo (confirmação
    humana), nunca exceção que mata o comando do agente."""
    profile = resolve_login_profile("EPROC")
    page = FakePage(set(), quebrados={"#infraBarraSuperior"})
    assert detect_page_state(page, profile) == "inconclusive"


def test_handlers_nao_tem_mais_marcadores_de_substring():
    """A fonte única é login_profiles; marcador duplicado não pode voltar."""
    from app.local_agent import handlers

    with open(handlers.__file__, encoding="utf-8") as arquivo:
        conteudo = arquivo.read()
    assert "_LOGIN_MARKERS" not in conteudo
    assert "_AUTHENTICATED_MARKERS" not in conteudo
