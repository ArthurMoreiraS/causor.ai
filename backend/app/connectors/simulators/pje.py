"""Simulador sanitizado do PJe."""

from __future__ import annotations

from app.connectors.simulators.base import CourtSimulator


def build() -> CourtSimulator:
    return CourtSimulator(
        sistema="PJe",
        login_marker="Certificado digital",
        panel_marker="Painel do Advogado",
        secret_label="Documento sigiloso",
    )
