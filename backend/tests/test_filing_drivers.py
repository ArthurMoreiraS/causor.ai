"""TDD for the per-system filing driver dispatch."""

import pytest

from app.connectors.drivers import (
    UnsupportedFilingSystemError,
    get_filing_driver,
)
from app.connectors.pje.connector import PjeFilingPackage


def _package(numero="0000001-00.2024.8.26.0100"):
    return PjeFilingPackage(
        peticao_id=1, processo_id=1, numero_processo=numero,
        tribunal="TJSP", orgao_julgador="1a Vara", tipo_peticao="Manifestacao",
        conteudo="minuta", credencial_id=7,
    )


def test_sandbox_driver_returns_protocol_deterministically():
    driver = get_filing_driver("e-SAJ", mode="sandbox")
    checkpoint = driver.prepare_filing(_package(), submit=True)
    assert checkpoint.checkpoint == "protocolado"
    assert checkpoint.irreversible is True
    assert checkpoint.evidence["protocolo"]
    assert checkpoint.evidence["sistema"] == "e-SAJ"
    assert checkpoint.evidence["states"]  # passos do agente
    # determinístico: mesmo processo/sistema -> mesmo protocolo
    again = get_filing_driver("e-SAJ", mode="sandbox").prepare_filing(_package(), submit=True)
    assert again.evidence["protocolo"] == checkpoint.evidence["protocolo"]


def test_sandbox_ready_to_sign_when_not_submitting():
    checkpoint = get_filing_driver("PJe", mode="sandbox").prepare_filing(_package(), submit=False)
    assert checkpoint.checkpoint == "ready_to_sign"
    assert checkpoint.irreversible is False
    assert "protocolo" not in checkpoint.evidence


def test_real_mode_rejects_system_without_driver():
    with pytest.raises(UnsupportedFilingSystemError):
        get_filing_driver("e-SAJ", mode="real")


def test_real_mode_pje_returns_pje_driver():
    driver = get_filing_driver("PJe", mode="real")
    assert driver.sistema == "PJe"
