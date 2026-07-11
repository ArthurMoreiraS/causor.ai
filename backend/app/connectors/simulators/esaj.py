"""Simulador sanitizado do e-SAJ."""

from __future__ import annotations

from app.connectors.simulators.base import CourtSimulator


def build() -> CourtSimulator:
    return CourtSimulator(
        sistema="e-SAJ",
        login_marker="Certificado digital",
        panel_marker="Portal e-SAJ · Advogado",
        secret_label="Documento restrito",
    )
