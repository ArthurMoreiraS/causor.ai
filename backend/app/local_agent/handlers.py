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
INCONCLUSIVE_BEFORE_PROMPT_SECONDS = 30.0

# Injetado só na janela local do agente, na máquina do advogado. Monta um
# elemento e seta uma flag — não faz requisição nenhuma nem altera qualquer
# coisa no sistema do tribunal.
_BANNER_SCRIPT = """
(() => {
  if (document.getElementById('causor-confirm-banner')) return;
  window.causorLoginConfirmed = false;
  const bar = document.createElement('div');
  bar.id = 'causor-confirm-banner';
  bar.style.cssText = 'position:fixed;z-index:2147483647;left:0;right:0;bottom:0;'
    + 'background:#111;color:#fff;font:14px system-ui;padding:12px 16px;'
    + 'display:flex;gap:12px;align-items:center;justify-content:center';
  const text = document.createElement('span');
  text.textContent = 'Causor não conseguiu confirmar o login automaticamente.';
  const button = document.createElement('button');
  button.textContent = 'Já estou logado';
  button.style.cssText = 'background:#fff;color:#111;border:0;border-radius:6px;'
    + 'padding:6px 14px;cursor:pointer;font-weight:600';
  button.onclick = () => { window.causorLoginConfirmed = true; bar.remove(); };
  bar.appendChild(text); bar.appendChild(button);
  document.body.appendChild(bar);
})();
"""


def _install_confirm_banner(page) -> None:
    """Injeta o pedido de confirmação na janela local do agente.

    Falha silenciosa de propósito: se a página não aceita script, o login
    segue esperando a detecção automática até o timeout — o banner é rede de
    segurança, não pode virar mais um jeito de o comando morrer.
    """
    try:
        page.evaluate(_BANNER_SCRIPT)
    except Exception:
        return


def _confirm_clicked(page) -> bool:
    try:
        return bool(page.evaluate("window.causorLoginConfirmed === true"))
    except Exception:
        return False


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
        inconclusive_since: float | None = None
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
            if state == "inconclusive":
                # Sistema sem perfil, ou perfil que não bateu (tribunal que
                # nunca vimos): pergunta ao advogado, que já está na frente
                # da janela, em vez de estourar o timeout.
                now = time.monotonic()
                if inconclusive_since is None:
                    inconclusive_since = now
                elif now - inconclusive_since >= INCONCLUSIVE_BEFORE_PROMPT_SECONDS:
                    _install_confirm_banner(page)
                    if _confirm_clicked(page):
                        return {
                            "session_ready": True,
                            "version_marker": None,
                            "evidence": {
                                "final_url_host": _safe_host(page.url),
                                "confirmed_by": "human",
                            },
                        }
            else:
                inconclusive_since = None
            time.sleep(POLL_SECONDS)
    return {"session_ready": False, "error_code": "login_timeout"}


def handle_check_court_session(payload: dict) -> dict:
    """Confere headless se o perfil persistente ainda está autenticado.

    ``session_alive=None`` quando não dá para afirmar (perfil travado por uma
    janela aberta do advogado, seletor que mudou, sistema sem perfil): o
    backend mantém o estado atual em vez de marcar expirado.
    """
    from app.local_agent.browser import persistent_court_context

    sistema = payload["sistema"]
    profile = resolve_login_profile(sistema)
    if profile is None:
        return {"session_alive": None, "error_code": "sem_perfil_de_login"}

    try:
        with persistent_court_context(
            root=agent_config.profiles_root(),
            sistema=sistema,
            tribunal=payload["tribunal"],
            grau=payload["grau"],
            url=payload["url_login"],
            headed=False,
        ) as (_context, page):
            state = detect_page_state(page, profile)
    except Exception:
        # Perfil em uso pelo navegador aberto do advogado é o caso comum.
        return {"session_alive": None, "error_code": "profile_locked"}

    if state == "authenticated":
        return {"session_alive": True}
    if state == "login":
        return {"session_alive": False, "error_code": "session_expired"}
    return {"session_alive": None, "error_code": f"check_{state}"}


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
        "check_court_session": handle_check_court_session,
        "read_process": handle_read_process,
        "prepare_filing": handle_prepare_filing,
    }
