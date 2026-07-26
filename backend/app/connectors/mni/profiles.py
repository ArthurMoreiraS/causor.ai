"""Endpoints MNI por (tribunal, grau).

**Só entra aqui endpoint confirmado.** Falha de MNI marca a captura ``failed``
e *não* cai para o agente local (ver ``executor.run_mni_capture_job``): um
endpoint palpitado manda o advogado para um erro em vez do caminho que
funciona. Sem entrada, o MNI está indisponível para a rota (fail-closed) e a
captura vai pelo agente — que é o comportamento correto para tribunal
desconhecido.

Confirmação = o host serviu ``wsdl:definitions`` com o namespace
``servico-intercomunicacao-2.2.2`` e expôs ``consultarProcesso`` +
``entregarManifestacaoProcessual``. Varredura de 2026-07-22 sobre TJs, TRFs e
TRTs; ver ``docs/areas/mni-credenciamento.md`` para a lista completa, os
padrões de URL testados e os tribunais que responderam 403 (WAF) — 403 não
prova ausência de MNI, prova ausência de confirmação.

WSDL acessível ainda não é serviço funcional: só o credenciamento real, com o
teste opt-in ``RUN_MNI_LIVE=1``, promove um tribunal a utilizável de fato.
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
        tribunal=tribunal.upper(), grau=grau, url_endpoint=url_endpoint, verificado=True
    )


# --- Justica Estadual -------------------------------------------------------
_register("TJAP", "1", "https://pje.tjap.jus.br/1g/intercomunicacao")
_register("TJAP", "2", "https://pje.tjap.jus.br/2g/intercomunicacao")
_register("TJES", "1", "https://pje.tjes.jus.br/pje/intercomunicacao")
_register("TJMT", "1", "https://pje.tjmt.jus.br/pje/intercomunicacao")
_register("TJPA", "1", "https://pje.tjpa.jus.br/pje/intercomunicacao")
_register("TJPE", "1", "https://pje.tjpe.jus.br/1g/intercomunicacao")
_register("TJPE", "2", "https://pje.tjpe.jus.br/2g/intercomunicacao")
_register("TJPI", "1", "https://pje.tjpi.jus.br/1g/intercomunicacao")
_register("TJPI", "2", "https://pje.tjpi.jus.br/2g/intercomunicacao")
_register("TJRR", "1", "https://pje.tjrr.jus.br/pje/intercomunicacao")

# --- Justica Federal --------------------------------------------------------
_register("TRF5", "1", "https://pje.trf5.jus.br/pje/intercomunicacao")
_register("TRF5", "2", "https://pje2g.trf5.jus.br/pje/intercomunicacao")
_register("TRF6", "1", "https://pje1g.trf6.jus.br/pje/intercomunicacao")
_register("TRF6", "2", "https://pje2g.trf6.jus.br/pje/intercomunicacao")

# --- Justica do Trabalho ----------------------------------------------------
# Nenhum TRT confirmado: o padrao CSJT
# (``/primeirograu/servicosweb/mni222/intercomunicacao``) responde 403 em toda
# a varredura, o que e consistente com WAF na frente do webservice. Registrar
# por padrao mandaria captura trabalhista para um endpoint nao confirmado —
# fica fora ate o credenciamento confirmar a URL de um TRT concreto.


def resolve_mni_profile(tribunal: str | None, grau: str) -> MniEndpointProfile | None:
    if not tribunal or grau not in ("1", "2"):
        return None
    return _PROFILES.get((tribunal.strip().upper(), grau))


def known_mni_profiles() -> list[MniEndpointProfile]:
    return sorted(_PROFILES.values(), key=lambda p: (p.tribunal, p.grau))
