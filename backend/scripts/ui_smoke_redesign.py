"""Smoke visual do redesign Handle: telas principais nos 2 temas.

Uso: python scripts/ui_smoke_redesign.py [dir_saida]
Pressupõe frontend em :3000, backend em :8000 e credenciais em
CAUSOR_SMOKE_EMAIL / CAUSOR_SMOKE_PASSWORD (conta de piloto/demo).
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

out = Path(sys.argv[1] if len(sys.argv) > 1 else "shots/redesign")
out.mkdir(parents=True, exist_ok=True)

email = os.environ["CAUSOR_SMOKE_EMAIL"]
password = os.environ["CAUSOR_SMOKE_PASSWORD"]

VIEWS = ["Dashboard", "Intimações", "Processos", "Prazos", "Minutas", "Protocolos", "Conectores", "Auditoria"]

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:3000", wait_until="networkidle")
    if page.get_by_placeholder("voce@escritorio.com.br").count() or page.locator("input[type=email]").count():
        page.locator("input[type=email]").fill(email)
        page.locator("input[type=password]").fill(password)
        page.get_by_role("button", name="Entrar").click()
        page.wait_for_timeout(2500)

    for theme in ("light", "dark"):
        page.evaluate(
            "t => { if (t === 'dark') document.documentElement.dataset.theme = 'dark';"
            " else delete document.documentElement.dataset.theme; }",
            theme,
        )
        for view in VIEWS:
            page.get_by_role("button", name=view, exact=True).first.click()
            page.wait_for_timeout(900)
            slug = view.lower().replace("ç", "c").replace("õ", "o").replace("á", "a")
            page.screenshot(path=str(out / f"{theme}-{slug}.png"))

    browser.close()

print(f"screenshots em {out.resolve()}")
