"""Registro tribunal+grau -> sistema + URLs de login/peticionamento.

O sistema processual e a URL de peticionamento sao propriedade do *tribunal*
(e do grau). Este registro e best-effort e sobreponivel: sistemas migram
(ex.: TJSP inicia migracao para eproc em 2025; TJPR migrou de Projudi para
eproc), entao entradas conferidas contra o site oficial carregam
``verificado=True`` e as demais sao palpite a confirmar (``verificado=False``).
DataJud, quando traz o campo, e autoritativo e sobrepoe o palpite.

Para PJe/eproc nao ha URL distinta de "peticionamento": o advogado loga e
peticiona dentro dos autos, a partir do painel. Nesses sistemas
``url_peticionamento`` cai para ``url_login``. Para o e-SAJ ha uma URL de
peticionamento intermediario propria por grau (parametro ``servico``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CourtRoute:
    tribunal: str
    grau: str
    sistema: str
    url_login: str | None
    url_peticionamento: str | None
    verificado: bool
    observacao: str | None = None


# Cada entrada: sistema + (opcional) login/pet por grau + verificado + obs.
# login/pet sao dicts {"1": ..., "2": ...}; ausencia de pet cai para login.
_ROUTES: dict[str, dict] = {
    # --- e-SAJ (Softplan) ---
    "TJSP": {
        "sistema": "e-SAJ",
        "login": {
            "1": "https://esaj.tjsp.jus.br/esaj/portal.do?servico=740000",
            "2": "https://esaj.tjsp.jus.br/esaj/portal.do?servico=740000",
        },
        "pet": {
            "1": "https://esaj.tjsp.jus.br/esaj?servico=820100",
            "2": "https://esaj.tjsp.jus.br/esaj?servico=820200",
        },
        "verificado": True,
    },
    "TJMS": {"sistema": "e-SAJ", "verificado": False},
    "TJCE": {"sistema": "e-SAJ", "verificado": False},
    "TJAL": {"sistema": "e-SAJ", "verificado": False},
    "TJAC": {"sistema": "e-SAJ", "verificado": False},
    # --- PJe (explicito e verificado; demais TJs/TRTs/TRFs caem no default PJe) ---
    "TJMG": {
        "sistema": "PJe",
        "login": {
            "1": "https://pje.tjmg.jus.br/pje/login.seam",
            "2": "https://pje2g.tjmg.jus.br/pje/login.seam",
        },
        "verificado": True,
        "obs": "2o grau na instancia pje2g",
    },
    "TJDFT": {
        "sistema": "PJe",
        "login": {
            "1": "https://pje.tjdft.jus.br/pje/login.seam",
            "2": "https://pje2i.tjdft.jus.br/pje/login.seam",
        },
        "verificado": True,
        "obs": "2o grau na instancia pje2i (segunda instancia)",
    },
    "TJBA": {
        "sistema": "PJe",
        "login": {
            "1": "https://pje.tjba.jus.br/pje/login.seam",
            "2": "https://pje2g.tjba.jus.br/pje/login.seam",
        },
        "verificado": True,
    },
    "TJPE": {
        "sistema": "PJe",
        "login": {
            "1": "https://pje.tjpe.jus.br/1g/login.seam",
            "2": "https://pje.tjpe.jus.br/2g/login.seam",
        },
        "verificado": True,
    },
    "TJPA": {
        "sistema": "PJe",
        "login": {
            "1": "https://pje.tjpa.jus.br/pje/login.seam",
            "2": "https://pje.tjpa.jus.br/pje-2g/login.seam",
        },
        "verificado": True,
        "obs": "pje-2g cobre 2o grau e turmas recursais",
    },
    "TJMA": {
        "sistema": "PJe",
        "login": {
            "1": "https://pje.tjma.jus.br/pje/login.seam",
            "2": "https://pje2.tjma.jus.br/pje2g/login.seam",
        },
        "verificado": True,
    },
    "TJMT": {
        "sistema": "PJe",
        "login": {
            "1": "https://pje.tjmt.jus.br/pje/login.seam",
            "2": "https://pje2.tjmt.jus.br/pje2/login.seam",
        },
        "verificado": True,
    },
    # TRFs em PJe seguem o padrao pje1g/pje2g.<trf>.jus.br (TRF2 usa eproc;
    # TRF4 esta na secao EPROC). Conferidos contra os portais oficiais.
    "TRF1": {
        "sistema": "PJe",
        "login": {
            "1": "https://pje1g.trf1.jus.br/pje/login.seam",
            "2": "https://pje2g.trf1.jus.br/pje/login.seam",
        },
        "verificado": True,
    },
    "TRF3": {
        "sistema": "PJe",
        "login": {
            "1": "https://pje1g.trf3.jus.br/pje/login.seam",
            "2": "https://pje2g.trf3.jus.br/pje/login.seam",
        },
        "verificado": True,
    },
    "TRF5": {
        "sistema": "PJe",
        "login": {
            "1": "https://pje1g.trf5.jus.br/pje/login.seam",
            "2": "https://pje2g.trf5.jus.br/pje/login.seam",
        },
        "verificado": True,
        "obs": "PJe 2.x; legado 1.x em pje.trf5.jus.br para processos antigos",
    },
    "TRF6": {
        "sistema": "PJe",
        "login": {
            "1": "https://pje1g.trf6.jus.br/pje/login.seam",
            "2": "https://pje2g.trf6.jus.br/pje/login.seam",
        },
        "verificado": True,
    },
    # --- EPROC ---
    "TJRS": {
        "sistema": "EPROC",
        "login": {
            "1": "https://eproc1g.tjrs.jus.br/eproc/externo_controlador.php?acao=principal",
            "2": "https://eproc2g.tjrs.jus.br/eproc/externo_controlador.php?acao=principal",
        },
        "verificado": True,
    },
    "TRF4": {
        "sistema": "EPROC",
        "login": {"2": "https://eproc.trf4.jus.br/eproc2trf4/"},
        "verificado": True,
        "obs": "1o grau federal por secao (JFRS/JFSC/JFPR)",
    },
    "TJSC": {"sistema": "EPROC", "verificado": False},
    "TJTO": {"sistema": "EPROC", "verificado": False},
    # --- Projudi ---
    "TJPR": {
        "sistema": "Projudi",
        "verificado": False,
        "obs": "migrou para eproc; Projudi legado",
    },
    "TJGO": {"sistema": "Projudi", "verificado": False},
}

# Justica do Trabalho: os 24 TRTs usam PJe no padrao CSJT
# pje.trt<N>.jus.br/{primeirograu,segundograu}/login.seam. Conferidos contra o
# portal oficial: TRT1, TRT2, TRT3 e TRT15; os demais seguem o padrao (palpite
# forte a confirmar no primeiro uso).
_TRT_CONFERIDOS = {1, 2, 3, 15}
for _n in range(1, 25):
    _ROUTES[f"TRT{_n}"] = {
        "sistema": "PJe",
        "login": {
            "1": f"https://pje.trt{_n}.jus.br/primeirograu/login.seam",
            "2": f"https://pje.trt{_n}.jus.br/segundograu/login.seam",
        },
        "verificado": _n in _TRT_CONFERIDOS,
    }


def known_routes() -> list[CourtRoute]:
    """Todas as rotas conhecidas (tribunal x grau) do registro.

    Base para a matriz de cobertura: cada rota vira um perfil candidato que
    nasce ``experimental`` e só a validação live promove."""
    routes: list[CourtRoute] = []
    for sigla, cfg in _ROUTES.items():
        graus = sorted(set(cfg.get("login", {}).keys()) | {"1"})
        for grau in graus:
            route = resolve_route(sigla, grau)
            if route is not None:
                routes.append(route)
    return routes


def resolve_route(tribunal: str | None, grau: str = "1") -> CourtRoute | None:
    """Resolve ``(tribunal, grau)`` para sistema + URLs; ``None`` sem tribunal.

    Tribunal desconhecido cai no default ``PJe`` sem URL (o cadastro/registro
    confirma depois; o fallback manual cobre o protocolo).
    """
    if not tribunal or not tribunal.strip():
        return None
    sigla = tribunal.strip().upper()
    grau = grau if grau in ("1", "2") else "1"

    cfg = _ROUTES.get(sigla)
    if cfg is None:
        return CourtRoute(
            tribunal=sigla, grau=grau, sistema="PJe",
            url_login=None, url_peticionamento=None, verificado=False,
        )

    login_map = cfg.get("login", {})
    url_login = login_map.get(grau) or login_map.get("1") or None
    pet_map = cfg.get("pet", {})
    # PJe/eproc peticionam a partir do painel -> peticionamento = login.
    url_peticionamento = pet_map.get(grau) or pet_map.get("1") or url_login
    return CourtRoute(
        tribunal=sigla, grau=grau, sistema=cfg["sistema"],
        url_login=url_login, url_peticionamento=url_peticionamento,
        verificado=bool(cfg.get("verificado")), observacao=cfg.get("obs"),
    )
