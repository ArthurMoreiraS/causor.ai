"""Prazos cabíveis por natureza do ato e rito, com fundamento legal.

O modelo só classifica o ato (sentença, acórdão...) e o rito; a duração vem
daqui, de forma determinística e auditável. O resultado é sempre uma sugestão a
conferir: o cabimento concreto (interesse recursal, hipótese do art. 1.015,
prazo em dobro da parte representada) depende do advogado.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

CATALOG_VERSION = "prazos_por_ato_v1_2026-10-07"

CPC = "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm"
JEC = "https://www.planalto.gov.br/ccivil_03/leis/l9099.htm"
CLT = "https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452.htm"

ATOS = (
    "sentenca",
    "acordao",
    "decisao_interlocutoria",
    "decisao_monocratica_tribunal",
    "inadmissao_recurso_excepcional",
    "intimacao_manifestacao",
    "pauta_julgamento",
    "distribuicao_ou_expediente",
    "citacao",
    "outro",
)
RITOS = ("comum", "juizado", "trabalhista", "criminal", "outro", "incerto")

# Atos que, por natureza, não abrem prazo para a parte.
SEM_PRAZO = {
    "pauta_julgamento": "Intimação de pauta de julgamento: não abre prazo processual para a parte.",
    "distribuicao_ou_expediente": "Comunicação de distribuição ou expediente: não abre prazo processual para a parte.",
}


@dataclass(frozen=True)
class Candidato:
    ato_cabivel: str
    dias: int
    fundamento: str
    fonte: str

    def as_dict(self) -> dict:
        return asdict(self)


def _ed(fundamento: str = "CPC, art. 1.023", fonte: str = CPC) -> Candidato:
    return Candidato("Embargos de declaração", 5, fundamento, fonte)


_CATALOGO: dict[tuple[str, str], tuple[Candidato, ...]] = {
    ("sentenca", "comum"): (
        Candidato("Apelação", 15, "CPC, arts. 1.003, § 5º, e 1.009", CPC),
        _ed(),
    ),
    ("acordao", "comum"): (
        Candidato("Recurso especial / extraordinário", 15, "CPC, arts. 1.003, § 5º, e 1.029", CPC),
        _ed(),
    ),
    ("decisao_interlocutoria", "comum"): (
        Candidato("Agravo de instrumento (se cabível no art. 1.015)", 15, "CPC, arts. 1.003, § 5º, e 1.015", CPC),
        _ed(),
    ),
    ("decisao_monocratica_tribunal", "comum"): (
        Candidato("Agravo interno", 15, "CPC, arts. 1.003, § 5º, e 1.021", CPC),
        _ed(),
    ),
    ("inadmissao_recurso_excepcional", "comum"): (
        Candidato("Agravo em REsp/RE (art. 1.042) ou agravo interno (art. 1.030, § 2º), conforme o fundamento",
                  15, "CPC, arts. 1.003, § 5º, 1.030, § 2º, e 1.042", CPC),
        _ed(),
    ),
    ("intimacao_manifestacao", "comum"): (
        Candidato("Manifestação (prazo legal supletivo)", 5, "CPC, art. 218, § 3º", CPC),
    ),
    ("sentenca", "juizado"): (
        Candidato("Recurso inominado", 10, "Lei 9.099/1995, art. 42", JEC),
        _ed("Lei 9.099/1995, art. 49", JEC),
    ),
    ("acordao", "juizado"): (
        Candidato("Recurso extraordinário", 15, "CPC, arts. 1.003, § 5º, e 1.029", CPC),
        _ed("Lei 9.099/1995, art. 49", JEC),
    ),
    ("decisao_monocratica_tribunal", "juizado"): (
        Candidato("Agravo interno", 15, "CPC, arts. 1.003, § 5º, e 1.021, e regimento da turma", CPC),
        _ed("Lei 9.099/1995, art. 49", JEC),
    ),
    ("inadmissao_recurso_excepcional", "juizado"): (
        Candidato("Agravo em RE (art. 1.042) ou agravo interno (art. 1.030, § 2º), conforme o fundamento",
                  15, "CPC, arts. 1.003, § 5º, 1.030, § 2º, e 1.042", CPC),
        _ed("Lei 9.099/1995, art. 49", JEC),
    ),
    ("intimacao_manifestacao", "juizado"): (
        Candidato("Manifestação (prazo legal supletivo)", 5, "CPC, art. 218, § 3º", CPC),
    ),
    ("sentenca", "trabalhista"): (
        Candidato("Recurso ordinário", 8, "CLT, art. 895, I", CLT),
        _ed("CLT, art. 897-A", CLT),
    ),
    ("acordao", "trabalhista"): (
        Candidato("Recurso de revista", 8, "CLT, art. 896", CLT),
        _ed("CLT, art. 897-A", CLT),
    ),
    ("decisao_monocratica_tribunal", "trabalhista"): (
        Candidato("Agravo interno", 8, "Lei 5.584/1970, art. 6º, e regimento do tribunal", CLT),
        _ed("CLT, art. 897-A", CLT),
    ),
    ("inadmissao_recurso_excepcional", "trabalhista"): (
        Candidato("Agravo de instrumento", 8, "CLT, art. 897, b", CLT),
        _ed("CLT, art. 897-A", CLT),
    ),
}


def candidatos(ato: str, rito: str) -> tuple[Candidato, ...]:
    """Prazos cabíveis, o principal primeiro. Vazio quando não há regra segura.

    Rito criminal, incerto ou desconhecido nunca gera sugestão: contagem e
    prazos são de outro regime.
    """
    return _CATALOGO.get((ato, rito), ())


def sem_prazo(ato: str) -> str | None:
    return SEM_PRAZO.get(ato)
