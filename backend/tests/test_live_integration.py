"""Live integration tests against the real CNJ APIs.

Disabled by default — they hit the network and depend on external availability.
Run explicitly with:

    RUN_LIVE=1 pytest tests/test_live_integration.py

DataJud additionally needs a public CNJ key in CAUSOR_DATAJUD_API_KEY.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

from app.capture.datajud import DatajudClient, ProcessoDTO
from app.capture.djen import ComunicacaoDTO, DjenClient
from app.settings import settings

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE") != "1", reason="live tests run only when RUN_LIVE=1"
)


def test_djen_consultar_live():
    client = DjenClient()
    hoje = date.today()
    result = client.consultar(
        oab="12345",
        uf="SP",
        data_inicio=hoje - timedelta(days=7),
        data_fim=hoje,
        itens_por_pagina=5,
    )
    assert isinstance(result, list)
    assert all(isinstance(c, ComunicacaoDTO) for c in result)


def test_datajud_consultar_live():
    if not settings.datajud_api_key:
        pytest.skip("CAUSOR_DATAJUD_API_KEY not configured")
    client = DatajudClient()
    # A well-known public number; the call must succeed (None if not found).
    result = client.consultar_processo(
        "00008323520184013202", tribunal="trf1"
    )
    assert result is None or isinstance(result, ProcessoDTO)
