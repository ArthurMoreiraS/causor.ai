"""Validação de sessão PJe.

A regra de detecção **não** mora aqui: vem de
``app.connectors.login_profiles`` (fonte única, compartilhada com o agente
local). Antes, este módulo tinha sua própria lista de marcadores com
"processo" contando como autenticado — e essa palavra aparece na tela de
login de vários tribunais, então sessão morta passava como válida.
"""

from __future__ import annotations

from app.connectors.login_profiles import detect_page_state, resolve_login_profile
from app.connectors.pje.pages.errors import CaptchaDetectedError, PjeSessionInvalidError


class LoginPage:
    def __init__(self, page):
        self.page = page

    def ensure_session_valid(self) -> None:
        """Levanta se a sessão claramente não está autenticada.

        ``inconclusive`` não levanta: sem evidência não se afirma que a sessão
        morreu — derrubar sessão boa é pior que seguir e falhar adiante com
        erro específico.
        """
        profile = resolve_login_profile("PJe")
        if profile is None:  # pragma: no cover - perfil PJe é sempre registrado
            return
        state = detect_page_state(self.page, profile)
        if state == "captcha":
            raise CaptchaDetectedError("captcha detectado; advogado precisa assumir")
        if state == "login":
            raise PjeSessionInvalidError("sessao PJe expirada ou nao autenticada")
