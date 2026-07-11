"""Fábrica de simuladores sanitizados por família de sistema."""

from __future__ import annotations

from app.connectors.simulators import esaj, eproc, pje, projudi
from app.connectors.simulators.base import CourtSimulator, SimulatorDocument

_BUILDERS = {
    "PJe": pje.build,
    "EPROC": eproc.build,
    "e-SAJ": esaj.build,
    "Projudi": projudi.build,
}


def list_simulators() -> list[str]:
    return list(_BUILDERS)


def build_simulator(sistema: str) -> CourtSimulator:
    try:
        return _BUILDERS[sistema]()
    except KeyError:
        raise ValueError(f"sem simulador para o sistema {sistema!r}") from None


__all__ = ["CourtSimulator", "SimulatorDocument", "build_simulator", "list_simulators"]
