"""Simulador sanitizado do eproc."""

from __future__ import annotations

from app.connectors.simulators.base import CourtSimulator, SimulatorDocument, fake_pdf


def build() -> CourtSimulator:
    # eproc organiza documentos por evento; IDs combinam evento + documento.
    docs = [
        SimulatorDocument(
            external_id="SIM-DOC-001",
            nome="Evento 10 - Inicial.pdf",
            tipo="Petição inicial",
            page=1,
            pdf_bytes=fake_pdf("SIM-DOC-001"),
        ),
        SimulatorDocument(
            external_id="SIM-DOC-002",
            nome="Evento 11 - Decisão.pdf",
            tipo="Decisão",
            page=2,
            pdf_bytes=fake_pdf("SIM-DOC-002"),
        ),
        SimulatorDocument(
            external_id="SIM-DOC-003",
            nome="Evento 11 - Anexo restrito.pdf",
            tipo="Anexo",
            page=2,
            sigiloso=True,
            parent_external_id="SIM-DOC-002",
            pdf_bytes=fake_pdf("SIM-DOC-003"),
        ),
    ]
    return CourtSimulator(
        sistema="EPROC",
        login_marker="Certificado digital",
        panel_marker="Painel eproc",
        secret_label="Documento restrito",
        documents=docs,
    )
