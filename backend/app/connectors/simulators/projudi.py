"""Simulador sanitizado do Projudi."""

from __future__ import annotations

from app.connectors.simulators.base import CourtSimulator, SimulatorDocument, fake_pdf


def build() -> CourtSimulator:
    # Projudi identifica arquivos por movimentação (MOV-n-ARQ-m).
    docs = [
        SimulatorDocument(
            external_id="SIM-DOC-001",
            nome="Mov 5 - Inicial.pdf",
            tipo="Petição inicial",
            page=1,
            pdf_bytes=fake_pdf("SIM-DOC-001"),
        ),
        SimulatorDocument(
            external_id="SIM-DOC-002",
            nome="Mov 8 - Sentença.pdf",
            tipo="Sentença",
            page=2,
            pdf_bytes=fake_pdf("SIM-DOC-002"),
        ),
        SimulatorDocument(
            external_id="SIM-DOC-003",
            nome="Mov 8 - Anexo restrito.pdf",
            tipo="Anexo",
            page=2,
            sigiloso=True,
            parent_external_id="SIM-DOC-002",
            pdf_bytes=fake_pdf("SIM-DOC-003"),
        ),
    ]
    return CourtSimulator(
        sistema="Projudi",
        login_marker="Assinatura digital",
        panel_marker="Projudi · Área do Advogado",
        secret_label="Documento restrito",
        documents=docs,
    )
