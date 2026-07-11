"""Preparo de protocolo live (opt-in), sempre ``submit=False``. CI pula.

Nunca clica em assinar/protocolar durante descoberta: para em
``ready_to_sign`` e devolve o controle ao advogado.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_COURT_LIVE") != "1",
    reason="set RUN_COURT_LIVE=1 na maquina autorizada do advogado",
)


@pytest.fixture
def live_filing():
    from app.connectors.registry import get_connector_registry

    registry = get_connector_registry()
    driver_cls = registry.filing(
        os.environ["CAUSOR_LIVE_SYSTEM"],
        tribunal=os.environ["CAUSOR_LIVE_COURT"],
        grau=os.environ["CAUSOR_LIVE_DEGREE"],
    )
    return driver_cls()


def test_live_filing_stops_before_irreversible_click(live_filing):
    from app.connectors.contracts import FilingPackage

    pdf_path = os.environ["CAUSOR_LIVE_PETITION_PDF"]
    with open(pdf_path, "rb") as handle:
        pdf_bytes = handle.read()
    package = FilingPackage(
        peticao_id=1,
        processo_instancia_id=1,
        numero_processo=os.environ["CAUSOR_LIVE_PROCESS"],
        tribunal=os.environ["CAUSOR_LIVE_COURT"],
        sistema=os.environ["CAUSOR_LIVE_SYSTEM"],
        grau=os.environ["CAUSOR_LIVE_DEGREE"],
        tipo_peticao="Manifestação",
        pdf_bytes=pdf_bytes,
    )
    checkpoint = live_filing.prepare_filing(package, submit=False)
    assert checkpoint.checkpoint == "ready_to_sign"
    assert checkpoint.irreversible is False
