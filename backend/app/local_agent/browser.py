"""Perfis Playwright persistentes por (sistema, tribunal, grau).

O perfil (cookies, sessão do tribunal) vive somente na máquina do advogado,
em ``%LOCALAPPDATA%\\Causor\\profiles``; nunca entra no Git nem é enviado ao
backend.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import re

from playwright.sync_api import sync_playwright


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")


def profile_dir(root: Path, sistema: str, tribunal: str, grau: str) -> Path:
    if grau not in {"1", "2"}:
        raise ValueError("grau must be 1 or 2")
    return root / _slug(sistema) / _slug(tribunal) / grau


@contextmanager
def persistent_court_context(
    *, root: Path, sistema: str, tribunal: str, grau: str, url: str, headed: bool = True
):
    directory = profile_dir(root, sistema, tribunal, grau)
    directory.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(directory),
            headless=not headed,
            accept_downloads=True,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        try:
            yield context, page
        finally:
            context.close()
