"""Handlers de comando do agente local.

``open_court_login`` abre o portal do tribunal em janela headed na máquina do
advogado e espera o login acontecer. O desfecho reportado ao backend é apenas
``session_ready``/marcadores — a sessão fica no perfil local do navegador.
"""

from __future__ import annotations

import time

from app.local_agent import config as agent_config

LOGIN_WAIT_SECONDS = 300.0
POLL_SECONDS = 2.0

_LOGIN_MARKERS = ("entrar com gov.br", "certificado digital", "senha")
_AUTHENTICATED_MARKERS = ("logout", "sair", "painel", "minhas intimações", "meu painel")


def _page_state(content: str) -> str:
    lowered = content.lower()
    if "captcha" in lowered or "recaptcha" in lowered:
        return "captcha"
    authenticated = any(marker in lowered for marker in _AUTHENTICATED_MARKERS)
    unauthenticated = any(marker in lowered for marker in _LOGIN_MARKERS)
    if authenticated and not unauthenticated:
        return "authenticated"
    return "waiting"


def handle_open_court_login(payload: dict) -> dict:
    """Abre o portal e aguarda o advogado logar; nunca digita credencial."""
    from app.local_agent.browser import persistent_court_context

    sistema = payload["sistema"]
    tribunal = payload["tribunal"]
    grau = payload["grau"]
    url_login = payload["url_login"]

    with persistent_court_context(
        root=agent_config.profiles_root(),
        sistema=sistema,
        tribunal=tribunal,
        grau=grau,
        url=url_login,
        headed=True,
    ) as (_context, page):
        deadline = time.monotonic() + LOGIN_WAIT_SECONDS
        while time.monotonic() < deadline:
            state = _page_state(page.content())
            if state == "authenticated":
                return {
                    "session_ready": True,
                    "version_marker": None,
                    "evidence": {"final_url_host": _safe_host(page.url)},
                }
            if state == "captcha":
                return {"session_ready": False, "error_code": "captcha_required"}
            time.sleep(POLL_SECONDS)
    return {"session_ready": False, "error_code": "login_timeout"}


def _safe_host(url: str) -> str:
    """Só o host entra na evidência; nunca path/query (podem conter IDs)."""
    from urllib.parse import urlsplit

    return urlsplit(url).netloc


def handle_read_process(payload: dict) -> dict:
    """Leitura integral dos autos: resolvida pelos drivers reais das Tasks 6–9.

    Enquanto o perfil real não estiver registrado, falha fechado — nunca
    presume sucesso nem devolve manifesto vazio."""
    from app.connectors.registry import (
        UnsupportedConnectorProfile,
        get_connector_registry,
    )

    registry = get_connector_registry()
    try:
        registry.reader(payload["sistema"], tribunal=payload["tribunal"], grau=payload["grau"])
    except UnsupportedConnectorProfile as exc:
        raise RuntimeError(str(exc)) from exc
    raise NotImplementedError("read_process driver ainda não implementado para este perfil")


def handle_prepare_filing(payload: dict) -> dict:
    """Preparo/protocolo: resolvido pelos drivers reais das Tasks 6–9."""
    from app.connectors.registry import (
        UnsupportedConnectorProfile,
        get_connector_registry,
    )

    registry = get_connector_registry()
    try:
        registry.filing(payload["sistema"], tribunal=payload["tribunal"], grau=payload["grau"])
    except UnsupportedConnectorProfile as exc:
        raise RuntimeError(str(exc)) from exc
    raise NotImplementedError("prepare_filing driver ainda não implementado para este perfil")


def default_handlers() -> dict:
    return {
        "open_court_login": handle_open_court_login,
        "read_process": handle_read_process,
        "prepare_filing": handle_prepare_filing,
    }
