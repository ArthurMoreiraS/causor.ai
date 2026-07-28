"""Cliente SOAP MNI: parsing tolerante, erros canonicos, senha nunca vaza."""

import base64

import httpx
import pytest

from app.connectors.errors import (
    AccessDenied,
    DocumentDownloadFailed,
    InstanceNotFound,
    MniUnavailable,
)
from app.connectors.mni.client import MniClient

NS = (
    'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
    'xmlns:ns2="http://www.cnj.jus.br/intercomunicacao-2.2.2"'
)

RESPOSTA_LISTA = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope {NS}><soap:Body>
  <ns2:consultarProcessoResposta>
    <sucesso>true</sucesso>
    <mensagem>Processo consultado com sucesso</mensagem>
    <processo>
      <dadosBasicos numero="00000000000000000000" classeProcessual="7" nivelSigilo="0"/>
      <documento idDocumento="SIM-DOC-001" tipoDocumento="1" dataHora="20260701120000"
                 mimetype="application/pdf" nivelSigilo="0" descricao="Peticao inicial"/>
      <documento idDocumento="SIM-DOC-002" tipoDocumento="4" dataHora="20260702090000"
                 mimetype="application/pdf" nivelSigilo="0" descricao="Decisao">
        <documentoVinculado idDocumento="SIM-DOC-003" tipoDocumento="9"
                            dataHora="20260702090500" mimetype="application/pdf"
                            nivelSigilo="1" descricao="Anexo sigiloso"/>
      </documento>
    </processo>
  </ns2:consultarProcessoResposta>
</soap:Body></soap:Envelope>"""

PDF_B64 = base64.b64encode(b"%PDF-1.4\n%SIM-DOC-001\n%%EOF\n").decode("ascii")

RESPOSTA_CONTEUDO = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope {NS}><soap:Body>
  <ns2:consultarProcessoResposta>
    <sucesso>true</sucesso>
    <mensagem>ok</mensagem>
    <processo>
      <documento idDocumento="SIM-DOC-001" tipoDocumento="1" dataHora="20260701120000"
                 mimetype="application/pdf" nivelSigilo="0" descricao="Peticao inicial">
        <conteudo>{PDF_B64}</conteudo>
      </documento>
    </processo>
  </ns2:consultarProcessoResposta>
</soap:Body></soap:Envelope>"""

RESPOSTA_AUTH = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope {NS}><soap:Body>
  <ns2:consultarProcessoResposta>
    <sucesso>false</sucesso>
    <mensagem>Usuario ou senha invalidos</mensagem>
  </ns2:consultarProcessoResposta>
</soap:Body></soap:Envelope>"""


def _resposta_sem_sucesso(mensagem: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope {NS}><soap:Body>
  <ns2:consultarProcessoResposta>
    <sucesso>false</sucesso>
    <mensagem>{mensagem}</mensagem>
  </ns2:consultarProcessoResposta>
</soap:Body></soap:Envelope>"""


def _client(handler) -> MniClient:
    return MniClient(
        url_endpoint="https://mni.sim.jus.br/intercomunicacao",
        id_consultante="12345678900",
        senha="segredo-mni",
        transport=httpx.MockTransport(handler),
    )


def test_consultar_processo_parses_documents_and_nested_attachment():
    client = _client(lambda request: httpx.Response(200, content=RESPOSTA_LISTA.encode()))
    result = client.consultar_processo("0000000-00.2026.8.13.0000")
    assert result.sucesso is True
    ids = [d.id for d in result.documentos]
    assert ids == ["SIM-DOC-001", "SIM-DOC-002", "SIM-DOC-003"]
    anexo = result.documentos[2]
    assert anexo.parent_id == "SIM-DOC-002"
    assert anexo.nivel_sigilo == 1


def test_baixar_documentos_decodes_base64_content():
    client = _client(lambda request: httpx.Response(200, content=RESPOSTA_CONTEUDO.encode()))
    blobs = client.baixar_documentos("0000000-00.2026.8.13.0000", ["SIM-DOC-001"])
    assert blobs["SIM-DOC-001"].startswith(b"%PDF-")


def test_baixar_documentos_missing_content_raises_download_failed():
    client = _client(lambda request: httpx.Response(200, content=RESPOSTA_LISTA.encode()))
    with pytest.raises(DocumentDownloadFailed):
        client.baixar_documentos("0000000-00.2026.8.13.0000", ["SIM-DOC-001"])


def test_auth_failure_maps_to_access_denied():
    client = _client(lambda request: httpx.Response(200, content=RESPOSTA_AUTH.encode()))
    with pytest.raises(AccessDenied):
        client.consultar_processo("0000000-00.2026.8.13.0000")


@pytest.mark.parametrize(
    "mensagem",
    [
        "Processo nao encontrado",
        "Processo não encontrado",
        "Nao existe processo com o numero informado",
        "Processo inexistente neste grau",
        "Processo não localizado",
    ],
)
def test_processo_inexistente_no_grau_mapeia_para_instance_not_found(mensagem):
    """Grau que o processo não tem é ausência, não falha de layout.

    `LayoutUnknown` marcaria a captura `failed` e travaria o contexto; o
    executor precisa distinguir para selar `not_applicable`.
    """
    client = _client(
        lambda request: httpx.Response(200, content=_resposta_sem_sucesso(mensagem).encode())
    )
    with pytest.raises(InstanceNotFound):
        client.consultar_processo("0000000-00.2026.8.13.0000")


def test_nao_encontrado_por_falta_de_permissao_continua_access_denied():
    """Ambiguidade resolve para o lado seguro.

    Tratar negativa de acesso como "instância inexistente" selaria
    `not_applicable` e deixaria o contexto ficar `ready` sem os autos —
    exatamente o fail-open que o Plano 2 existe para impedir.
    """
    client = _client(
        lambda request: httpx.Response(
            200,
            content=_resposta_sem_sucesso(
                "Processo nao encontrado para o usuario informado"
            ).encode(),
        )
    )
    with pytest.raises(AccessDenied):
        client.consultar_processo("0000000-00.2026.8.13.0000")


def test_http_5xx_and_timeout_map_to_mni_unavailable():
    client = _client(lambda request: httpx.Response(503))
    with pytest.raises(MniUnavailable):
        client.consultar_processo("0000000-00.2026.8.13.0000")

    def _timeout(request):
        raise httpx.ConnectTimeout("boom")

    client = _client(_timeout)
    with pytest.raises(MniUnavailable):
        client.consultar_processo("0000000-00.2026.8.13.0000")


def test_senha_nunca_aparece_em_repr_nem_em_erros():
    client = _client(lambda request: httpx.Response(200, content=RESPOSTA_AUTH.encode()))
    assert "segredo-mni" not in repr(client)
    with pytest.raises(AccessDenied) as excinfo:
        client.consultar_processo("0000000-00.2026.8.13.0000")
    assert "segredo-mni" not in str(excinfo.value)


def test_request_envelope_contains_credentials_and_number():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content.decode()
        return httpx.Response(200, content=RESPOSTA_LISTA.encode())

    client = _client(handler)
    client.consultar_processo("0000000-00.2026.8.13.0000")
    assert "<ser:idConsultante>12345678900</ser:idConsultante>" in seen["body"]
    assert "00000000020268130000" in seen["body"]  # numero sanitizado (so digitos)
