"""PJe login/session detection page object."""

from __future__ import annotations

from app.connectors.pje.pages.errors import CaptchaDetectedError, PjeSessionInvalidError


class LoginPage:
    def __init__(self, page):
        self.page = page

    def ensure_session_valid(self) -> None:
        content = self.page.content().lower()
        if "captcha" in content or "recaptcha" in content:
            raise CaptchaDetectedError("captcha detectado; advogado precisa assumir")
        login_markers = ("entrar com gov.br", "certificado digital", "usuario", "usuário", "senha")
        authenticated_markers = ("logout", "sair", "painel", "processo")
        if any(marker in content for marker in login_markers) and not any(
            marker in content for marker in authenticated_markers
        ):
            raise PjeSessionInvalidError("sessao PJe expirada ou nao autenticada")
