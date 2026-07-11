"""Simuladores sanitizados: páginas sintéticas, sem dado real.

Estes testes rodam na CI (sem navegador): validam o conteúdo das páginas e o
conjunto fixo de documentos. O teste Playwright ponta-a-ponta é opt-in.
"""

from app.connectors.simulators import (
    build_simulator,
    list_simulators,
)


def test_every_family_has_a_simulator():
    assert set(list_simulators()) == {"PJe", "EPROC", "e-SAJ", "Projudi"}


def test_simulator_exposes_three_fixed_documents_with_nested_and_secret():
    sim = build_simulator("PJe")
    docs = sim.documents
    assert [d.external_id for d in docs] == ["SIM-DOC-001", "SIM-DOC-002", "SIM-DOC-003"]
    # um anexo aninhado e um documento sigiloso
    assert any(d.parent_external_id == "SIM-DOC-002" for d in docs)
    assert any(d.sigiloso for d in docs)
    # PDFs sintéticos, sem dado real
    for doc in docs:
        assert doc.pdf_bytes.startswith(b"%PDF-")
        assert b"%%EOF" in doc.pdf_bytes


def test_documents_span_two_enumeration_pages():
    sim = build_simulator("EPROC")
    pages = {doc.page for doc in sim.documents}
    assert pages == {1, 2}


def test_login_page_has_unauthenticated_marker_and_panel_has_authenticated():
    sim = build_simulator("e-SAJ")
    assert any(m in sim.login_html().lower() for m in ("certificado digital", "entrar"))
    panel = sim.panel_html().lower()
    assert any(m in panel for m in ("painel", "sair", "logout"))


def test_receipt_page_carries_protocol_number():
    sim = build_simulator("Projudi")
    receipt = sim.receipt_html(protocolo="SIM-PROTO-2026-0001")
    assert "SIM-PROTO-2026-0001" in receipt
    assert "protocolo" in receipt.lower()


def test_secret_document_shows_restricted_label():
    sim = build_simulator("EPROC")
    autos = sim.autos_html(page=1) + sim.autos_html(page=2)
    assert any(word in autos.lower() for word in ("restrito", "sigiloso"))
