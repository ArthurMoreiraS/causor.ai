"""Smoke visual das telas novas (Protocolos, Conectores, modal de protocolo).

Uso: python scripts/ui_smoke.py [diretorio_de_saida]
Pressupõe frontend em http://localhost:3000 e backend em :8000 com seed de demo.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

out = Path(sys.argv[1] if len(sys.argv) > 1 else "shots")
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:3000", wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.screenshot(path=str(out / "01-fila.png"))

    page.get_by_role("link", name="Protocolos").click()
    page.wait_for_timeout(1200)
    page.screenshot(path=str(out / "02-protocolos.png"))

    page.get_by_role("link", name="Conectores").click()
    page.wait_for_timeout(800)
    page.screenshot(path=str(out / "03-conectores.png"))

    page.get_by_role("link", name="Gate OAB").click()
    page.wait_for_timeout(1000)
    botoes = page.get_by_role("button", name="Protocolar")
    if botoes.count():
        botoes.first.click()
        page.wait_for_timeout(1200)
        page.screenshot(path=str(out / "04-modal-protocolo.png"))
    else:
        page.screenshot(path=str(out / "04-gate-sem-protocolar.png"))

    browser.close()

print(f"screenshots em {out.resolve()}")
