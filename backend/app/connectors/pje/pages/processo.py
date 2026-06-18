"""PJe process lookup page object."""

from __future__ import annotations

import re
import unicodedata

from app.connectors.pje.pages.errors import (
    CaptchaDetectedError,
    LayoutDesconhecidoError,
    ProcessoNaoEncontradoError,
)


def _only_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _ascii_lower(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", errors="ignore").decode("ascii").lower()


class ProcessoPage:
    def __init__(self, page):
        self.page = page

    def localizar(self, numero_processo: str) -> None:
        self._raise_if_captcha()
        digits = _only_digits(numero_processo)
        candidates = [
            self.page.get_by_label(re.compile("processo", re.I)),
            self.page.locator("input[name*='numeroProcesso' i]"),
            self.page.locator("input[id*='numeroProcesso' i]"),
            self.page.locator("input[placeholder*='processo' i]"),
        ]
        field = next((candidate for candidate in candidates if candidate.count() > 0), None)
        if field is None:
            raise LayoutDesconhecidoError("campo de busca de processo nao encontrado")

        field.first.fill(digits)
        search_buttons = [
            self.page.get_by_role("button", name=re.compile("pesquisar|buscar|consultar", re.I)),
            self.page.locator("button[type='submit']"),
            self.page.locator("input[type='submit']"),
        ]
        button = next((candidate for candidate in search_buttons if candidate.count() > 0), None)
        if button is None:
            raise LayoutDesconhecidoError("botao de pesquisa de processo nao encontrado")
        button.first.click()
        self.page.wait_for_load_state("networkidle")

        self._raise_if_captcha()
        content = self.page.content()
        normalized_content = _ascii_lower(content)
        if "nenhum registro" in normalized_content or "nao encontrado" in normalized_content:
            raise ProcessoNaoEncontradoError("processo nao encontrado no PJe")
        if numero_processo not in content and digits not in _only_digits(content):
            raise ProcessoNaoEncontradoError("processo nao apareceu no resultado da busca")
        result_links = [
            self.page.get_by_role("link", name=re.compile(re.escape(numero_processo), re.I)),
            self.page.get_by_text(numero_processo, exact=False),
            self.page.get_by_text(digits, exact=False),
        ]
        result = next((candidate for candidate in result_links if candidate.count() > 0), None)
        if result is None:
            raise LayoutDesconhecidoError("link do processo no resultado nao encontrado")
        result.first.click()
        self.page.wait_for_load_state("networkidle")
        self._raise_if_captcha()

    def _raise_if_captcha(self) -> None:
        content = self.page.content().lower()
        if "captcha" in content or "recaptcha" in content:
            raise CaptchaDetectedError("captcha detectado; advogado precisa assumir")
