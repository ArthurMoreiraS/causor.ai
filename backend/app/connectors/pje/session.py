"""Playwright browser session boundary for assisted PJe filing."""

from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse


class PjeSessionError(RuntimeError):
    """Raised when a PJe browser session cannot be created safely."""


TRAINING_HOST_TOKENS = (
    "homolog",
    "trein",
    "teste",
    "sandbox",
    "localhost",
    "127.0.0.1",
)


def validate_training_base_url(base_url: str) -> None:
    """Refuse production-looking PJe URLs unless explicitly enabled."""

    if os.getenv("CAUSOR_PJE_ALLOW_PROD") == "1":
        return
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    if not host:
        raise PjeSessionError("URL base do PJe invalida")
    if any(token in host for token in TRAINING_HOST_TOKENS):
        return
    raise PjeSessionError(
        "conector PJe real bloqueado fora de treino/homologacao; "
        "defina CAUSOR_PJE_ALLOW_PROD=1 para liberar explicitamente"
    )


@dataclass
class PjeBrowserSession:
    """Context manager that opens an isolated Playwright context from storage_state."""

    base_url: str
    storage_state: dict
    headless: bool = True

    def __enter__(self):
        validate_training_base_url(self.base_url)
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - depends on optional runtime install
            raise PjeSessionError(
                "Playwright nao esta instalado; instale as dependencias e rode playwright install"
            ) from exc

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context(
            base_url=self.base_url,
            storage_state=self.storage_state,
            accept_downloads=True,
        )
        self.page = self._context.new_page()
        self.page.goto(self.base_url, wait_until="domcontentloaded")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        for attr in ("_context", "_browser", "_playwright"):
            resource = getattr(self, attr, None)
            if resource is None:
                continue
            close = getattr(resource, "close", None) or getattr(resource, "stop", None)
            if close is not None:
                close()
