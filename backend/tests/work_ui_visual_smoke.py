"""Visual acceptance for the MVP work and assistant screens with synthetic data.

Requires the isolated demo API on 8099 and frontend on 3099.
"""
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


OUTPUT = Path(__file__).resolve().parents[1] / "artifacts" / "work-browser"
OUTPUT.mkdir(parents=True, exist_ok=True)


def encoded(value):
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")


user = {
    "id": str(uuid4()), "email": "demo@example.invalid", "aud": "authenticated",
    "role": "authenticated", "user_metadata": {"name": "DEMONSTRAÇÃO SINTÉTICA"},
}
expires = int(datetime.now(timezone.utc).timestamp()) + 3600
token = encoded({"alg": "HS256", "typ": "JWT"}) + "." + encoded({"sub": user["id"], "exp": expires}) + ".synthetic-signature"
session = {
    "access_token": token, "token_type": "bearer", "refresh_token": "synthetic-test",
    "expires_in": 3600, "expires_at": expires, "user": user,
}


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ.get("CAUSOR_TEST_BROWSER_EXECUTABLE"))
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.set_default_timeout(30000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.add_init_script("localStorage.setItem('sb-127-auth-token', " + json.dumps(json.dumps(session)) + ");")
    page.route("http://127.0.0.1:54321/**", lambda route: route.fulfill(json=user))
    try:
        page.goto("http://127.0.0.1:3099/", wait_until="networkidle")
        navigation = page.get_by_role("navigation", name="Módulos do Causor")
        expect(navigation.get_by_role("button", name="Assistente Causor")).to_be_visible()
        expect(navigation.get_by_role("button", name="Protocolos")).to_have_count(0)
        navigation.get_by_role("button", name="Trabalhos").click()
        expect(page.get_by_role("heading", name="Preparar trabalho")).to_be_visible()
        checkbox = page.get_by_label("Cadastrar processo manualmente")
        assert checkbox.bounding_box()["width"] <= 24, "checkbox expanded across form"
        assert page.locator(".legalWorkspace").bounding_box()["x"] >= 20, "work view lacks horizontal padding"
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "horizontal overflow on desktop"
        page.screenshot(path=str(OUTPUT / "mvp-trabalhos-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        expect(checkbox).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "horizontal overflow on mobile"
        page.screenshot(path=str(OUTPUT / "mvp-trabalhos-mobile.png"), full_page=True)
        page.get_by_role("navigation", name="Módulos do Causor").get_by_role("button", name="Assistente Causor").click()
        expect(page.get_by_role("heading", name="Pergunte sobre seus casos e próximos passos.")).to_be_visible()
        page.screenshot(path=str(OUTPUT / "mvp-assistente-mobile.png"), full_page=True)
        assert not errors, errors
        print("PASS: work layout on desktop/mobile; assistant visible; protocol hidden. Synthetic data only.")
    except Exception:
        page.screenshot(path=str(OUTPUT / "mvp-ui-failure.png"), full_page=True)
        raise
    finally:
        browser.close()
