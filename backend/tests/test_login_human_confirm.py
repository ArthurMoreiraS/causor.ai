"""Tribunal desconhecido não pode virar login_timeout."""

from app.local_agent import handlers


class FakePage:
    def __init__(self, clicked_after: int = 1):
        self.evaluated: list[str] = []
        self.calls = 0
        self.clicked_after = clicked_after
        self.url = "https://tribunal.exemplo/painel"

    def evaluate(self, script: str):
        self.evaluated.append(script)
        if "causorLoginConfirmed ===" in script:
            self.calls += 1
            return self.calls >= self.clicked_after
        return None


def test_banner_e_idempotente_no_proprio_script():
    """A guarda mora no JS, não no Python: se o advogado navegar, o banner
    some da página e precisa ser reinjetado. Bloquear no Python impediria
    isso; o script é que não pode duplicar o elemento."""
    page = FakePage()
    handlers._install_confirm_banner(page)
    handlers._install_confirm_banner(page)
    assert "getElementById('causor-confirm-banner')" in page.evaluated[0]
    assert len(page.evaluated) == 2  # reinjeção permitida de propósito


def test_banner_pergunta_em_portugues():
    page = FakePage()
    handlers._install_confirm_banner(page)
    assert "Já estou logado" in page.evaluated[0]


def test_banner_e_so_local_nao_envia_nada_ao_tribunal():
    """O script só monta um elemento e seta uma flag: nenhum fetch/XHR."""
    page = FakePage()
    handlers._install_confirm_banner(page)
    script = page.evaluated[0]
    for proibido in ("fetch(", "XMLHttpRequest", "navigator.sendBeacon", "form.submit"):
        assert proibido not in script


def test_confirmacao_humana_e_lida_do_flag():
    assert handlers._confirm_clicked(FakePage(clicked_after=1)) is True


def test_pagina_que_explode_nao_confirma_sozinha():
    class Explode:
        def evaluate(self, script: str):
            raise RuntimeError("sem javascript")

    assert handlers._confirm_clicked(Explode()) is False


def test_banner_que_explode_nao_derruba_o_login():
    class Explode:
        def evaluate(self, script: str):
            raise RuntimeError("sem javascript")

    handlers._install_confirm_banner(Explode())  # não levanta
