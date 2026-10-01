"""Narrow CPC duration catalog; no rule applies without matching notice text."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.deadline_interpretation import DeadlineInterpretation

CPC_URL = "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm"
CATALOG_VERSION = "cpc_2015_regras_prazo_v1_2026-10-01"


@dataclass(frozen=True)
class LegalRule:
    rule_id: str
    article: str
    paragraph: str
    days: int
    command_pattern: str
    source_url: str = CPC_URL
    version: str = CATALOG_VERSION


RULES = {
    "cpc_1010_1": LegalRule("cpc_1010_1", "1010", "1", 15,
        r"(?:intime-se|intimem-se|abra-se\s+vista\s+a|de-se\s+vista\s+a)\s+"
        r"(?:\w+\s+){0,8}(?:apelad\w*|parte\s+contraria)"
        r".{0,100}contrarrazoes\s+(?:de|a|da)\s+apelacao"),
    "cpc_1023_2": LegalRule("cpc_1023_2", "1023", "2", 5,
        r"(?:intime-se|intimem-se|abra-se\s+vista\s+a|de-se\s+vista\s+a)\s+"
        r"(?:\w+\s+){0,8}embargad\w*"
        r".{0,100}(?:manifest\w*|respon\w*).{0,70}embargos\s+de\s+declaracao"),
    "cpc_437_1": LegalRule("cpc_437_1", "437", "1", 15,
        r"(?:intime-se|intimem-se|abra-se\s+vista\s+a|de-se\s+vista\s+a)\s+"
        r"(?:\w+\s+){0,8}(?:parte\s+contraria|outra\s+parte)"
        r".{0,100}manifest\w*.{0,70}(?:document\w*\s+nov\w*|document\w*\s+juntad\w*)"),
}


def special_regime_in_official_context(*values: str) -> bool:
    """Official class/organ labels that preclude this narrow CPC civil count."""
    context = _plain(" ".join(values))
    return bool(re.search(r"\b(?:juizado|lei\s*9\.?099|clt|trabalhist\w*|criminal|penal|"
                          r"execucao\s+fiscal|mandado\s+de\s+seguranca)\b", context))


def _plain(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFD", value.lower())
                   if unicodedata.category(char) != "Mn")


def resolve_statutory_duration(result: DeadlineInterpretation, text: str) -> LegalRule | None:
    """Return a catalog rule only when command and exact paragraph are provable."""
    rule = RULES.get(result.regra_id or "")
    if rule is None or result.dias is not None or not result.comando or not result.citacao_normativa:
        return None
    command, citation = result.comando.strip(), result.citacao_normativa.strip()
    if command not in text or citation not in text or len(command) > 500 or len(citation) > 200:
        return None
    if not re.search(rule.command_pattern, _plain(command), re.DOTALL):
        return None
    norm = _plain(citation)
    article = rf"{rule.article[0]}\.?{rule.article[1:]}" if len(rule.article) == 4 else rule.article
    if not re.search(rf"\b(?:art\.?|artigo)\s*{article}\s*[,;:]?\s*"
                     rf"(?:§|paragrafo)\s*{rule.paragraph}\s*(?:o|º|°)?\b", norm):
        return None
    if not re.search(r"\bcpc\b|codigo\s+de\s+processo\s+civil", norm):
        return None
    # The cited command and paragraph must describe the same current order.
    if abs(text.index(command) - text.index(citation)) > 500:
        return None
    whole = _plain(text)
    if re.search(r"\b(?:juizado|lei\s*9\.?099|clt|trabalhist\w*|criminal|penal|"
                 r"execucao\s+fiscal|mandado\s+de\s+seguranca)\b", whole):
        return None
    if re.search(r"\b(?:nao|sem)\s+(?:intime-se|intimem-se)|"
                 r"\b(?:cancelo|revogo|torno\s+sem\s+efeito)\b", _plain(text[:text.index(citation)])):
        return None
    if re.search(r"[\"“”'«»]", command) or re.search(r"\b(?:alega|argumenta|sustenta|"
                 r"transcreve|citou|requereu|pediu)\b", _plain(text[:text.index(command)])):
        return None
    before, after = text[:text.index(command)], text[text.index(command) + len(command):]
    if before.count("“") > before.count("”") or before.count('"') % 2 or before.count("«") > before.count("»"):
        return None
    if after.lstrip().startswith(("”", '"', "»")):
        return None
    if re.search(r"\bdias?\b", whole):
        return None  # a judicial duration, including a conflicting one, needs its own proof
    if re.search(r"prazo\s+em\s+dobro|contagem\s+em\s+dobro|dilac\w*|prorrog\w*|"
                 r"intimacao\s+pessoal|ciencia\s+pessoal|prazo\s+comum|"
                 r"(?:fazenda\s+publica|ministerio\s+publico|defensoria\s+publica|litisconsort\w*)", whole):
        return None
    if re.search(r"transcri\w*|decisao\s+anterior|despacho\s+anterior|historico|"
                 r"(?:ja|foi)\s+intimad\w*", _plain(text[:text.index(command)])):
        return None
    if rule.rule_id == "cpc_437_1" and re.search(r"(?:art\.?\s*437.{0,30})?§\s*2\s*(?:o|º|°)?|"
                                                 r"prazo\s+(?:maior|diverso|ampliado)", whole):
        return None
    # Multiple commands are not safely represented by one deadline.
    outside = whole.replace(_plain(command), "", 1)
    if re.search(r"\b(?:tambem|ainda|ademais)\s+(?:intim\w*|manifest\w*)|"
                 r"\b(?:intime-se|intimem-se|cite-se)\b", outside):
        return None
    return rule
