"""TDD for DjenClient — mocked HTTP against the DJEN/Comunica API."""

from datetime import date

import httpx
import pytest

from app.capture.djen import ComunicacaoDTO, DjenClient

BASE = "https://comunicaapi.pje.jus.br/api/v1"

SAMPLE = {
    "status": "success",
    "message": "ok",
    "count": 2,
    "items": [
        {
            "id": 111,
            "numero_processo": "0000001-00.2024.8.26.0100",
            "siglaTribunal": "TJSP",
            "tipoComunicacao": "Intimação",
            "nomeOrgao": "1ª Vara Cível",
            "texto": "Fica a parte intimada para manifestar em 15 dias.",
            "data_disponibilizacao": "2024-09-06",
            "meio": "D",
            "link": "https://example/doc/111",
        },
        {
            "id": 112,
            "numero_processo": "0000002-00.2024.8.26.0100",
            "siglaTribunal": "TJSP",
            "tipoComunicacao": "Citação",
            "nomeOrgao": "2ª Vara Cível",
            "texto": "Citação para contestar.",
            "data_disponibilizacao": "2024-09-06",
            "meio": "D",
            "link": "https://example/doc/112",
        },
    ],
}


@pytest.fixture
def client():
    return DjenClient(http=httpx.Client(base_url=BASE))


def test_consultar_returns_dtos(httpx_mock, client):
    httpx_mock.add_response(json=SAMPLE)
    result = client.consultar(oab="12345", uf="SP")
    assert len(result) == 2
    assert all(isinstance(c, ComunicacaoDTO) for c in result)
    first = result[0]
    assert first.id == "111"
    assert first.numero_processo == "0000001-00.2024.8.26.0100"
    assert first.tribunal == "TJSP"
    assert first.tipo_comunicacao == "Intimação"
    assert first.data_disponibilizacao == date(2024, 9, 6)
    assert "intimada" in first.texto


def test_consultar_sends_oab_query_params(httpx_mock, client):
    httpx_mock.add_response(json=SAMPLE)
    client.consultar(oab="12345", uf="SP", data_inicio=date(2024, 9, 1))
    request = httpx_mock.get_requests()[0]
    assert request.url.params["numeroOab"] == "12345"
    assert request.url.params["ufOab"] == "SP"
    assert request.url.params["dataDisponibilizacaoInicio"] == "2024-09-01"


def test_consultar_preserves_raw_payload(httpx_mock, client):
    httpx_mock.add_response(json=SAMPLE)
    result = client.consultar(oab="12345", uf="SP")
    assert result[0].raw["nomeOrgao"] == "1ª Vara Cível"


def test_consultar_empty_items(httpx_mock, client):
    httpx_mock.add_response(json={"status": "success", "count": 0, "items": []})
    assert client.consultar(oab="999", uf="SP") == []


def test_http_error_raises(httpx_mock, client):
    httpx_mock.add_response(status_code=500)
    with pytest.raises(httpx.HTTPStatusError):
        client.consultar(oab="12345", uf="SP")
