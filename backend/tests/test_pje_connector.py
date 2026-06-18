"""Tests for the assisted PJe connector orchestration."""

import pytest

from app.connectors.pje.connector import (
    PjeAssistedConnector,
    PjeConnectorError,
    PjeFilingPackage,
)


def _package() -> PjeFilingPackage:
    return PjeFilingPackage(
        peticao_id=10,
        processo_id=20,
        numero_processo="0000001-00.2024.8.26.0100",
        tribunal="TJSP",
        orgao_julgador="1 Vara Civel",
        tipo_peticao="Manifestacao",
        conteudo="texto",
        credencial_id=30,
        pdf_bytes=b"%PDF fake",
        pje_base_url="https://pje-treinamento.tjsp.jus.br/pje",
        storage_state={"cookies": [], "origins": []},
    )


class FakeEvidence:
    def __init__(self):
        self.items = []

    def capture(self, page, label):
        self.items.append(label)
        return f"local://{label}.png"


class FakeSession:
    def __init__(self):
        self.closed = False
        self.page = object()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.closed = True


class FakeLoginPage:
    def __init__(self):
        self.called = False

    def ensure_session_valid(self):
        self.called = True


class FakeProcessoPage:
    def __init__(self):
        self.localized = []

    def localizar(self, numero_processo):
        self.localized.append(numero_processo)


class FakePeticionarPage:
    def __init__(self):
        self.calls = []

    def abrir_intermediaria(self):
        self.calls.append("abrir_intermediaria")

    def selecionar_tipo(self, tipo_peticao):
        self.calls.append(("selecionar_tipo", tipo_peticao))

    def anexar_pdf(self, *, filename, pdf_bytes):
        self.calls.append(("anexar_pdf", filename, pdf_bytes))

    def assert_ready_to_sign(self):
        self.calls.append("assert_ready_to_sign")
        return {"draft_url": "https://pje-treinamento.tjsp.jus.br/pje/rascunho/1"}


def test_prepare_filing_orchestrates_browser_flow_and_stops_before_signature():
    session = FakeSession()
    evidence = FakeEvidence()
    login = FakeLoginPage()
    processo = FakeProcessoPage()
    peticionar = FakePeticionarPage()

    connector = PjeAssistedConnector(
        session_factory=lambda **kwargs: session,
        login_page_factory=lambda page: login,
        processo_page_factory=lambda page: processo,
        peticionar_page_factory=lambda page: peticionar,
        evidence_store=evidence,
    )

    checkpoint = connector.prepare_filing(_package())

    assert checkpoint.checkpoint == "ready_to_sign"
    assert checkpoint.irreversible is False
    assert checkpoint.evidence["states"] == [
        "session_ok",
        "processo_localizado",
        "peticionamento_aberto",
        "tipo_selecionado",
        "minuta_anexada",
        "ready_to_sign",
    ]
    assert processo.localized == ["0000001-00.2024.8.26.0100"]
    assert peticionar.calls == [
        "abrir_intermediaria",
        ("selecionar_tipo", "Manifestacao"),
        ("anexar_pdf", "peticao-10.pdf", b"%PDF fake"),
        "assert_ready_to_sign",
    ]
    assert evidence.items == [
        "session_ok",
        "processo_localizado",
        "peticionamento_aberto",
        "tipo_selecionado",
        "minuta_anexada",
        "ready_to_sign",
    ]
    assert "assinar" not in str(peticionar.calls).lower()
    assert "protocol" not in str(peticionar.calls).lower()
    assert session.closed is True


def test_prepare_filing_requires_pdf_for_browser_automation():
    package = _package()
    package = PjeFilingPackage(
        peticao_id=package.peticao_id,
        processo_id=package.processo_id,
        numero_processo=package.numero_processo,
        tribunal=package.tribunal,
        orgao_julgador=package.orgao_julgador,
        tipo_peticao=package.tipo_peticao,
        conteudo=package.conteudo,
        credencial_id=package.credencial_id,
        pje_base_url=package.pje_base_url,
        storage_state=package.storage_state,
    )
    connector = PjeAssistedConnector(session_factory=lambda **kwargs: FakeSession())

    with pytest.raises(PjeConnectorError, match="PDF"):
        connector.prepare_filing(package)
