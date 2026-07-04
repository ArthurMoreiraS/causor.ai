"""TDD for DatajudClient — mocked Elasticsearch-style DataJud API."""

from datetime import date

import httpx
import pytest

from app.capture.datajud import DatajudClient, ProcessoDTO

BASE = "https://api-publica.datajud.cnj.jus.br"

SAMPLE = {
    "hits": {
        "total": {"value": 1},
        "hits": [
            {
                "_source": {
                    "numeroProcesso": "00000010020248260100",
                    "classe": {"codigo": 7, "nome": "Procedimento Comum Cível"},
                    "tribunal": "TJSP",
                    "dataAjuizamento": "2024-01-15T00:00:00.000Z",
                    "orgaoJulgador": {"codigo": 1, "nome": "1ª Vara Cível"},
                    "sistema": {"codigo": 1, "nome": "PJe"},
                    "movimentos": [
                        {"codigo": 26, "nome": "Distribuição", "dataHora": "2024-01-15T10:00:00.000Z"},
                        {"codigo": 51, "nome": "Conclusão", "dataHora": "2024-02-01T14:30:00.000Z"},
                    ],
                    "assuntos": [{"codigo": 1127, "nome": "Inadimplemento"}],
                }
            }
        ],
    }
}


@pytest.fixture
def client():
    return DatajudClient(api_key="test-key", http=httpx.Client(base_url=BASE))


def test_consultar_processo_returns_dto(httpx_mock, client):
    httpx_mock.add_response(json=SAMPLE)
    proc = client.consultar_processo("00000010020248260100", tribunal="tjsp")
    assert isinstance(proc, ProcessoDTO)
    assert proc.numero_processo == "00000010020248260100"
    assert proc.classe == "Procedimento Comum Cível"
    assert proc.tribunal == "TJSP"
    assert proc.data_ajuizamento == date(2024, 1, 15)
    assert proc.orgao_julgador == "1ª Vara Cível"
    assert proc.sistema == "PJe"
    assert len(proc.movimentos) == 2
    assert proc.movimentos[0].codigo == 26
    assert proc.movimentos[0].nome == "Distribuição"


def test_consultar_processo_accepts_compact_data_ajuizamento(httpx_mock, client):
    sample = {
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_source": {
                        **SAMPLE["hits"]["hits"][0]["_source"],
                        "dataAjuizamento": "20260408000000",
                    }
                }
            ],
        }
    }
    httpx_mock.add_response(json=sample)

    proc = client.consultar_processo("00000010020248260100", tribunal="stj")

    assert proc is not None
    assert proc.data_ajuizamento == date(2026, 4, 8)


def test_hits_endpoint_and_auth_header(httpx_mock, client):
    httpx_mock.add_response(json=SAMPLE)
    client.consultar_processo("00000010020248260100", tribunal="tjsp")
    request = httpx_mock.get_requests()[0]
    assert request.url.path == "/api_publica_tjsp/_search"
    assert request.method == "POST"
    assert request.headers["Authorization"] == "APIKey test-key"


def test_no_hits_returns_none(httpx_mock, client):
    httpx_mock.add_response(json={"hits": {"total": {"value": 0}, "hits": []}})
    assert client.consultar_processo("0000000", tribunal="tjsp") is None


def test_http_error_raises(httpx_mock, client):
    httpx_mock.add_response(status_code=401)
    with pytest.raises(httpx.HTTPStatusError):
        client.consultar_processo("0000000", tribunal="tjsp")


def test_consultar_processo_retries_read_timeout(httpx_mock):
    client = DatajudClient(
        api_key="test-key",
        http=httpx.Client(base_url=BASE),
        max_attempts=2,
        backoff_seconds=0,
    )
    httpx_mock.add_exception(httpx.ReadTimeout("The read operation timed out"))
    httpx_mock.add_response(json=SAMPLE)

    proc = client.consultar_processo("00000010020248260100", tribunal="tjsp")

    assert proc is not None
    assert proc.numero_processo == "00000010020248260100"
    assert len(httpx_mock.get_requests()) == 2


@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
def test_consultar_processo_retries_transient_status_codes(httpx_mock, status_code):
    """DataJud aplica rate limit (429) e sobrecarrega (5xx) sob rajada de
    consultas -- essas sao transientes e devem ser retentadas, nao so falhas
    de conexao/timeout."""
    client = DatajudClient(
        api_key="test-key",
        http=httpx.Client(base_url=BASE),
        max_attempts=2,
        backoff_seconds=0,
    )
    httpx_mock.add_response(status_code=status_code)
    httpx_mock.add_response(json=SAMPLE)

    proc = client.consultar_processo("00000010020248260100", tribunal="tjsp")

    assert proc is not None
    assert len(httpx_mock.get_requests()) == 2


def test_consultar_processo_gives_up_after_max_retries_on_429(httpx_mock):
    client = DatajudClient(
        api_key="test-key",
        http=httpx.Client(base_url=BASE),
        max_attempts=2,
        backoff_seconds=0,
    )
    httpx_mock.add_response(status_code=429)
    httpx_mock.add_response(status_code=429)

    with pytest.raises(httpx.HTTPStatusError):
        client.consultar_processo("00000010020248260100", tribunal="tjsp")

    assert len(httpx_mock.get_requests()) == 2
