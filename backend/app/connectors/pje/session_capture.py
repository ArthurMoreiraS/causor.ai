"""Assisted capture of a PJe authenticated Playwright storage_state."""

from __future__ import annotations

from app.connectors.pje.session import PjeSessionError, validate_training_base_url


def capture_pje_storage_state(
    *,
    base_url: str,
    timeout_seconds: int = 300,
    headless: bool = False,
) -> dict:
    """Open PJe for a human login and return Playwright storage_state.

    The lawyer authenticates directly in PJe. This function never asks for or
    receives PJe password, certificate files, private keys, or OTP values.
    """

    validate_training_base_url(base_url)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - depends on optional runtime install
        raise PjeSessionError(
            "Playwright nao esta instalado; instale as dependencias e rode playwright install"
        ) from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.goto(base_url, wait_until="domcontentloaded")
        print("Janela do PJe aberta. Faca o login diretamente no PJe.")
        print("Quando o painel do advogado carregar, volte aqui e pressione Enter.")
        input()
        page.wait_for_load_state("domcontentloaded", timeout=timeout_seconds * 1000)
        state = context.storage_state()
        browser.close()
        return state
