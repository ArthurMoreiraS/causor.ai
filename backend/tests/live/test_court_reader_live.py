"""Leitura live read-only (opt-in). CI sempre pula.

Requer ``RUN_COURT_LIVE=1`` na máquina autorizada do advogado, com o perfil
do agente local já logado no tribunal. Enumera duas vezes e prova que o
manifesto é estável e completo antes de qualquer promoção de perfil.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_COURT_LIVE") != "1",
    reason="set RUN_COURT_LIVE=1 na maquina autorizada do advogado",
)


@pytest.fixture
def live_target():
    from app.connectors.contracts import CourtTarget

    return CourtTarget(
        processo_instancia_id=1,
        processo_id=1,
        numero_processo=os.environ["CAUSOR_LIVE_PROCESS"],
        sistema=os.environ["CAUSOR_LIVE_SYSTEM"],
        tribunal=os.environ["CAUSOR_LIVE_COURT"],
        grau=os.environ["CAUSOR_LIVE_DEGREE"],
        url_base=os.environ.get("CAUSOR_LIVE_URL", ""),
    )


@pytest.fixture
def live_reader(live_target):
    from app.connectors.registry import get_connector_registry

    registry = get_connector_registry()
    driver_cls = registry.reader(
        live_target.sistema, tribunal=live_target.tribunal, grau=live_target.grau
    )
    return driver_cls()


def test_live_reader_returns_stable_complete_manifest(live_reader, live_target):
    first = live_reader.enumerate_documents(live_target)
    second = live_reader.enumerate_documents(live_target)
    assert first.cursor_complete is True
    assert first.source_fingerprint == second.source_fingerprint
    assert first.documentos
