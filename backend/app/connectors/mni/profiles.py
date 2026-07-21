"""Endpoints MNI por (tribunal, grau).

Padrão PJe: ``https://<host-do-grau>/pje/intercomunicacao``. Entradas nascem
``verificado=False`` — palpite forte a conferir no credenciamento; sem
entrada, o MNI está indisponível para a rota (fail-closed) e a captura cai
no agente local. Espelha o desenho best-effort de
``capture/court_routing.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MniEndpointProfile:
    tribunal: str
    grau: str
    url_endpoint: str
    versao: str = "2.2.2"
    verificado: bool = False


_PROFILES: dict[tuple[str, str], MniEndpointProfile] = {}


def _register(tribunal: str, grau: str, url_endpoint: str) -> None:
    key = (tribunal.upper(), grau)
    _PROFILES[key] = MniEndpointProfile(
        tribunal=tribunal.upper(), grau=grau, url_endpoint=url_endpoint
    )


# PJe estadual conferível contra court_routing (mesmos hosts por grau).
_register("TJMG", "1", "https://pje.tjmg.jus.br/pje/intercomunicacao")
_register("TJMG", "2", "https://pje2g.tjmg.jus.br/pje/intercomunicacao")
_register("TJDFT", "1", "https://pje.tjdft.jus.br/pje/intercomunicacao")
_register("TJDFT", "2", "https://pje2i.tjdft.jus.br/pje/intercomunicacao")
_register("TJBA", "1", "https://pje.tjba.jus.br/pje/intercomunicacao")
_register("TJBA", "2", "https://pje2g.tjba.jus.br/pje/intercomunicacao")
_register("TJPE", "1", "https://pje.tjpe.jus.br/1g/intercomunicacao")
_register("TJPE", "2", "https://pje.tjpe.jus.br/2g/intercomunicacao")

# Justica do Trabalho: padrao CSJT por grau.
for _n in range(1, 25):
    _register(f"TRT{_n}", "1", f"https://pje.trt{_n}.jus.br/primeirograu/intercomunicacao")
    _register(f"TRT{_n}", "2", f"https://pje.trt{_n}.jus.br/segundograu/intercomunicacao")


def resolve_mni_profile(tribunal: str | None, grau: str) -> MniEndpointProfile | None:
    if not tribunal or grau not in ("1", "2"):
        return None
    return _PROFILES.get((tribunal.strip().upper(), grau))


def known_mni_profiles() -> list[MniEndpointProfile]:
    return sorted(_PROFILES.values(), key=lambda p: (p.tribunal, p.grau))
