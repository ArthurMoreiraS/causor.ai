"""Opt-in Playwright integration test against the local fake PJe page."""

from __future__ import annotations

import os
import threading

import pytest

from app.connectors.pje.connector import PjeAssistedConnector, PjeFilingPackage
from app.connectors.pje.simulator import FAKE_PROCESSO, build_server


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PJE_SIMULATOR") != "1",
    reason="set RUN_PJE_SIMULATOR=1 to run Playwright against the local fake PJe",
)


def test_connector_reaches_ready_to_sign_against_local_pje_simulator():
    try:
        from playwright.sync_api import Error as PlaywrightError  # noqa: F401
    except ImportError:
        pytest.skip("Playwright is not installed")

    server = build_server(port=0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        connector = PjeAssistedConnector()
        checkpoint = connector.prepare_filing(
            PjeFilingPackage(
                peticao_id=1,
                processo_id=1,
                numero_processo=FAKE_PROCESSO,
                tribunal="SIM",
                orgao_julgador="Vara simulada",
                tipo_peticao="Manifestacao",
                conteudo="Manifestacao de teste.",
                pdf_bytes=b"%PDF-1.4\n%%EOF\n",
                pje_base_url=f"http://{host}:{port}",
                storage_state={"cookies": [], "origins": []},
            )
        )
    except Exception as exc:
        message = str(exc).lower()
        if "executable doesn't exist" in message or "browser" in message:
            pytest.skip("Playwright browser binaries are not installed")
        raise
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert checkpoint.checkpoint == "ready_to_sign"
    assert checkpoint.irreversible is False
    assert checkpoint.evidence["states"][-1] == "ready_to_sign"
