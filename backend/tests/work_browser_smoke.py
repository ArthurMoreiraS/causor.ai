"""Reproducible synthetic MVP browser acceptance; requires isolated demo servers.

Frontend: dummy Supabase at 127.0.0.1:54321, API at 127.0.0.1:8099, port 3099.
Backend: python -m tests.work_demo_server. Run: python -m tests.work_browser_smoke.
"""
import base64
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
from uuid import uuid4

import fitz
from playwright.sync_api import sync_playwright, expect

OUTPUT = Path(__file__).resolve().parents[1] / "artifacts" / "work-browser"
OUTPUT.mkdir(parents=True, exist_ok=True)
NUMBER = f"{uuid4().int % 10000000:07d}-12.2026.8.26.0100"


def pdf(path, texts):
    with fitz.open() as document:
        for text in texts:
            page = document.new_page()
            page.insert_textbox((40, 40, 540, 780), text, fontsize=12)
        document.save(path)


pdf(OUTPUT / "autos-sinteticos.pdf", [
    "DEMONSTRACAO SINTETICA - SEM EFEITO JUDICIAL\nCONTRATO FICTICIO\nA empresa ficticia contratou servicos em 01/08/2026. Valor previsto: R$ 1.000,00. As partes divergem sobre o pagamento.",
    "DEMONSTRACAO SINTETICA - SEM EFEITO JUDICIAL\nALEGACAO DE PAGAMENTO\nA parte afirma ter transferido o valor. O comprovante integral nao foi juntado. Esta pagina deve ser conferida antes da redacao.",
    "DEMONSTRACAO SINTETICA - SEM EFEITO JUDICIAL\nMANIFESTACAO CONTRARIA\nA parte contraria nega a quitacao e solicita comprovante bancario. Nenhuma conclusao juridica real decorre deste exemplo.",
])
pdf(OUTPUT / "comprovante-sintetico.pdf", [f"DEMONSTRACAO SINTETICA - NAO E RECIBO REAL\nProcesso: {NUMBER}\nProtocolo: DEMO-123\nData: 20/09/2026 14:00\nDestino: Vara de demonstracao\nArquivo: 01-peticao.pdf"])
pdf(OUTPUT / "comprovante-divergente.pdf", ["DEMONSTRACAO SINTETICA\nProcesso: 0000999-11.2026.8.26.0100\nProtocolo: OUTRO-123"])


def encode(value):
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")


user = {"id": str(uuid4()), "email": "demo@example.invalid", "aud": "authenticated", "role": "authenticated", "user_metadata": {"name": "DEMONSTRAÇÃO SINTÉTICA"}}
expires = int(datetime.now(timezone.utc).timestamp()) + 3600
token = encode({"alg": "HS256", "typ": "JWT"}) + "." + encode({"sub": user["id"], "exp": expires}) + ".synthetic-signature"
session = {"access_token": token, "token_type": "bearer", "refresh_token": "synthetic-test", "expires_in": 3600, "expires_at": expires, "user": user}

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ.get("CAUSOR_TEST_BROWSER_EXECUTABLE"))
    page = browser.new_page(viewport={"width": 1440, "height": 1050})
    page.set_default_timeout(30000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.add_init_script("localStorage.setItem('sb-127-auth-token', " + json.dumps(json.dumps(session)) + ");")
    page.route("http://127.0.0.1:54321/**", lambda route: route.fulfill(json=user))
    try:
        page.goto("http://127.0.0.1:3099/", wait_until="networkidle")
        navigation = page.get_by_role("navigation", name="Módulos do Causor")
        expect(navigation.get_by_role("button", name="Visão geral")).to_be_visible()
        expect(navigation.get_by_role("button", name="Intimações")).to_be_visible()
        expect(navigation.get_by_role("button", name="Trabalhos")).to_be_visible()
        expect(navigation.get_by_role("button", name="Assistente Causor")).to_be_visible()
        expect(navigation.get_by_role("button", name="Protocolos")).to_have_count(0)
        expect(page.get_by_role("button", name=re.compile(r"Contexto.*autos e documentos"))).to_be_visible()
        expect(page.get_by_text("DJEN", exact=True)).to_be_visible()
        page.screenshot(path=str(OUTPUT / "00-visao-geral-restaurada.png"), full_page=True)
        navigation.get_by_role("button", name="Trabalhos").click()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "horizontal overflow in work view"
        page.screenshot(path=str(OUTPUT / "00a-trabalhos-vazio.png"), full_page=True)
        page.get_by_label("Cadastrar processo manualmente").check()
        page.get_by_label("Número CNJ", exact=True).fill(NUMBER)
        page.get_by_label("Tribunal informado").fill("TJSP")
        page.get_by_label("Ou cadastrar cliente pelo nome").fill("Cliente sintético de demonstração")
        page.get_by_label("Providência", exact=True).fill("Manifestação sintética sobre pagamento")
        page.get_by_label("Instruções para o trabalho").fill("Conferir a prova de pagamento e a manifestação contrária. Demonstração sem efeito judicial.")
        page.get_by_label("Polo representado").fill("Autor")
        page.get_by_role("button", name="Criar trabalho", exact=True).click()
        page.get_by_role("navigation", name="Etapas deste trabalho").get_by_role("button", name="Documentos").click()
        expect(page.locator("#work-documents")).to_be_focused()
        page.get_by_role("button", name="Receber documentos", exact=True).click()
        page.get_by_label("Arquivos PDF").set_input_files(str(OUTPUT / "autos-sinteticos.pdf"))
        page.get_by_role("button", name="Enviar documentos", exact=True).click()
        expect(page.get_by_role("dialog")).to_have_count(0)
        expect(page.get_by_text("Envio pelo advogado", exact=True)).to_be_visible()
        page.get_by_label("Grau dos autos").select_option("2")
        page.get_by_text("O processo não possui autos no 2º grau", exact=True).click()
        page.get_by_label("Justificativa da ausência de autos").fill("Caso sintético de demonstração restrito ao primeiro grau; ausência declarada somente para este teste.")
        page.get_by_role("button", name="Registrar declaração", exact=True).click()
        expect(page.get_by_text("Contexto disponível para revisão", exact=True)).to_be_visible(timeout=45000)
        page.get_by_text("Declarar o acervo e identificar peças dentro dos PDFs", exact=True).click()
        page.get_by_label("Data de referência do acervo").fill("2026-09-20")
        page.get_by_label("Declaração de cobertura e limitações").fill("PDF sintético com contrato, alegação de pagamento e manifestação contrária. Não representa autos reais nem consulta ao tribunal.")
        page.get_by_label("Origem informada").select_option("autos_enviados")
        page.get_by_role("button", name="Identificar peça no PDF").click()
        page.get_by_label("Nome da peça").fill("Contrato fictício")
        page.get_by_role("button", name="Registrar escopo e índice").click()
        expect(page.get_by_role("button", name="Preparar análise das evidências")).to_be_enabled()
        page.screenshot(path=str(OUTPUT / "01-trabalho-documentos.png"), full_page=True)
        page.get_by_label("Pontos que precisam ser respondidos").fill("Há prova de pagamento?\nO que a parte contrária afirma?")
        page.get_by_role("button", name="Preparar análise das evidências", exact=True).click()
        page.get_by_role("button", name="Criar pendência documental").click()
        expect(page.get_by_text(re.compile(r"Pendência #\d+ vinculada ao trabalho"))).to_be_visible()
        page.get_by_label("Conferi as fontes, os pontos contrários e as lacunas desta análise.").check()
        page.get_by_role("button", name="Registrar conferência", exact=True).click()
        page.get_by_role("button", name="Gerar minuta para revisão", exact=True).click()
        expect(page.get_by_label("Conteúdo da minuta")).to_contain_text("DEMONSTRAÇÃO")
        page.screenshot(path=str(OUTPUT / "02-minuta-fontes.png"), full_page=True, animations="disabled")
        page.get_by_role("button", name="Continuar no trabalho", exact=True).click()
        page.reload(wait_until="networkidle")
        expect(page.get_by_role("heading", name="Minuta vinculada")).to_be_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        expect(page.get_by_role("navigation", name="Módulos do Causor").get_by_role("button", name="Trabalhos")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "horizontal overflow on mobile"
        page.screenshot(path=str(OUTPUT / "03-retomada-mobile.png"), full_page=True)
        assert not errors, errors
        print("PASS: manual intake, upload, scope, original sources, gap task, evidence review, draft, reload and mobile. Synthetic providers only.")
    except Exception:
        page.screenshot(path=str(OUTPUT / "failure.png"), full_page=True)
        (OUTPUT / "failure.html").write_text(page.content(), encoding="utf-8")
        raise
    finally:
        browser.close()
