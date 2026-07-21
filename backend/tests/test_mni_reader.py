from datetime import date

import pytest

from app.connectors.contracts import CourtTarget
from app.connectors.errors import DocumentDownloadFailed
from app.connectors.mni.client import MniConsultaResult, MniDocumentoMeta
from app.connectors.mni.reader import MniReaderDriver

TARGET = CourtTarget(
    processo_instancia_id=1,
    processo_id=1,
    numero_processo="0000000-00.2026.8.13.0000",
    sistema="PJe",
    tribunal="TJMG",
    grau="1",
    url_base="https://pje.tjmg.jus.br",
)

_DOCS = (
    MniDocumentoMeta(id="SIM-DOC-001", tipo="1", descricao="Peticao inicial",
                     data_hora="20260701120000", mimetype="application/pdf", nivel_sigilo=0),
    MniDocumentoMeta(id="SIM-DOC-002", tipo="4", descricao="Decisao",
                     data_hora="20260702090000", mimetype="application/pdf", nivel_sigilo=0),
    MniDocumentoMeta(id="SIM-DOC-003", tipo="9", descricao="Anexo sigiloso",
                     data_hora="20260702090500", mimetype="application/pdf",
                     nivel_sigilo=1, parent_id="SIM-DOC-002"),
)


class FakeClient:
    def __init__(self):
        self.download_calls: list[list[str]] = []

    def consultar_processo(self, numero):
        return MniConsultaResult(
            sucesso=True, mensagem="ok", documentos=_DOCS, conteudo_inline=False
        )

    def baixar_documentos(self, numero, ids):
        self.download_calls.append(list(ids))
        return {doc_id: b"%PDF-1.4\n%" + doc_id.encode() + b"\n%%EOF\n" for doc_id in ids}


def test_enumerate_produces_complete_snapshot_with_stable_fingerprint():
    driver = MniReaderDriver(FakeClient())
    first = driver.enumerate_documents(TARGET)
    second = driver.enumerate_documents(TARGET)
    assert first.cursor_complete is True
    assert first.source_fingerprint == second.source_fingerprint
    assert [d.external_id for d in first.documentos] == [
        "SIM-DOC-001", "SIM-DOC-002", "SIM-DOC-003"
    ]
    assert first.documentos[2].sigiloso is True
    assert first.documentos[2].parent_external_id == "SIM-DOC-002"
    assert first.documentos[0].data_documento == date(2026, 7, 1)
    assert first.evidence["fonte"] == "mni"


def test_prefetch_batches_and_download_serves_from_cache():
    client = FakeClient()
    driver = MniReaderDriver(client, batch_size=2)
    snapshot = driver.enumerate_documents(TARGET)
    driver.prefetch(TARGET, snapshot.documentos)
    assert client.download_calls == [["SIM-DOC-001", "SIM-DOC-002"], ["SIM-DOC-003"]]
    data = driver.download_document(TARGET, snapshot.documentos[0])
    assert data.startswith(b"%PDF-")
    assert client.download_calls == [["SIM-DOC-001", "SIM-DOC-002"], ["SIM-DOC-003"]]


def test_download_without_prefetch_fetches_single_document():
    client = FakeClient()
    driver = MniReaderDriver(client)
    snapshot = driver.enumerate_documents(TARGET)
    driver.download_document(TARGET, snapshot.documentos[1])
    assert client.download_calls == [["SIM-DOC-002"]]


def test_download_failure_propagates_canonical_error():
    class FailingClient(FakeClient):
        def baixar_documentos(self, numero, ids):
            raise DocumentDownloadFailed("sem teor")

    driver = MniReaderDriver(FailingClient())
    snapshot = driver.enumerate_documents(TARGET)
    with pytest.raises(DocumentDownloadFailed):
        driver.download_document(TARGET, snapshot.documentos[0])
