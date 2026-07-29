"""Handlers de comando do agente local.

``open_court_login`` abre o portal do tribunal em janela headed na máquina do
advogado e espera o login acontecer. O desfecho reportado ao backend é apenas
``session_ready``/marcadores — a sessão fica no perfil local do navegador.

A detecção de estado vem de ``app.connectors.login_profiles`` (fonte única,
por seletor visível). **Não reintroduzir marcadores de substring aqui**: a
lista anterior exigia a ausência da palavra "senha" para confirmar o login, e
painel logado tem "Alterar Senha" no menu — o advogado logava e o agente
girava até o timeout.
"""

from __future__ import annotations

import time

from app.connectors.login_profiles import detect_page_state, resolve_login_profile
from app.local_agent import config as agent_config

LOGIN_WAIT_SECONDS = 300.0
POLL_SECONDS = 2.0


def handle_open_court_login(payload: dict) -> dict:
    """Abre o portal e aguarda o advogado logar; nunca digita credencial."""
    from app.local_agent.browser import persistent_court_context

    sistema = payload["sistema"]
    tribunal = payload["tribunal"]
    grau = payload["grau"]
    url_login = payload["url_login"]
    profile = resolve_login_profile(sistema)

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
            state = "inconclusive" if profile is None else detect_page_state(page, profile)
            if state == "authenticated":
                return {
                    "session_ready": True,
                    "version_marker": None,
                    "evidence": {
                        "final_url_host": _safe_host(page.url),
                        "confirmed_by": "selector",
                    },
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
