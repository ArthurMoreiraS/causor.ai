"""Dossiê de uma OAB: o que já existe na carteira do advogado, hoje.

Serve a duas coisas ao mesmo tempo. É o T3' do plano de 90 dias — provar que o
entregável presta, com material real — e é a peça de prospecção: o DJEN é
público e nacional, então o quadro de intimações e prazos de um advogado se monta
sem credencial, sem pareamento e sem conector. É o único artefato do produto que
não pede nada a quem ainda não é cliente.

**Não recalcula a regra de alerta.** O nível vem de ``alertas.radar.classificar``,
a mesma função que o painel (``GET /alertas``) e o e-mail consomem. Um segundo
ponto de decisão faria o dossiê discordar da tela sobre o mesmo prazo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alertas import radar
from app.sor import models

JANELA_PADRAO_DIAS = 15


@dataclass(frozen=True)
class LinhaDossie:
    numero_processo: str | None
    tribunal: str | None
    tipo_comunicacao: str | None
    data_publicacao: date | None
    data_fatal: date | None
    dias_para_vencer: int | None
    nivel: str | None


@dataclass(frozen=True)
class Dossie:
    oab: str
    uf: str
    hoje: date
    janela_dias: int
    total_intimacoes: int
    total_com_prazo: int
    total_em_alerta: int
    linhas: list[LinhaDossie]


def _prazo_aberto_mais_proximo(intimacao: models.Intimacao) -> models.Prazo | None:
    abertos = [prazo for prazo in intimacao.prazos if not prazo.cumprido]
    if not abertos:
        return None
    return min(abertos, key=lambda prazo: prazo.data_fatal)


def montar_dossie(
    session: Session,
    *,
    escritorio_id: int,
    oab: str,
    uf: str,
    hoje: date,
    janela_dias: int = JANELA_PADRAO_DIAS,
) -> Dossie:
    """Monta o quadro da carteira dentro da janela, do prazo mais urgente ao menos."""
    inicio = hoje - timedelta(days=janela_dias)
    stmt = select(models.Intimacao).where(
        models.Intimacao.escritorio_id == escritorio_id
    )

    linhas: list[LinhaDossie] = []
    com_prazo = 0
    em_alerta = 0
    for intimacao in session.scalars(stmt):
        # Publicação é o que o advogado enxerga; disponibilização é o fallback de
        # quem publica sem a data final preenchida.
        publicacao = intimacao.data_publicacao or intimacao.data_disponibilizacao
        if publicacao is None or publicacao < inicio:
            continue
        prazo = _prazo_aberto_mais_proximo(intimacao)
        dias: int | None = None
        nivel: str | None = None
        if prazo is not None:
            com_prazo += 1
            dias = (prazo.data_fatal - hoje).days
            if dias <= radar.JANELA_DIAS:
                nivel = radar.classificar(dias)
                em_alerta += 1
        linhas.append(
            LinhaDossie(
                numero_processo=intimacao.numero_processo,
                tribunal=intimacao.tribunal,
                tipo_comunicacao=intimacao.tipo_comunicacao,
                data_publicacao=publicacao,
                data_fatal=prazo.data_fatal if prazo is not None else None,
                dias_para_vencer=dias,
                nivel=nivel,
            )
        )

    linhas.sort(
        key=lambda linha: (linha.data_fatal is None, linha.data_fatal or date.max)
    )
    return Dossie(
        oab=oab,
        uf=uf.upper(),
        hoje=hoje,
        janela_dias=janela_dias,
        total_intimacoes=len(linhas),
        total_com_prazo=com_prazo,
        total_em_alerta=em_alerta,
        linhas=linhas,
    )


def _celula(valor: object) -> str:
    if valor is None:
        return "—"
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor)


def renderizar_markdown(dossie: Dossie) -> str:
    """Uma página que cabe num WhatsApp e não promete o que não foi conferido."""
    linhas = [
        f"# Intimações da OAB {dossie.oab}/{dossie.uf}",
        "",
        f"Janela: últimos {dossie.janela_dias} dias · referência {dossie.hoje.isoformat()}",
        "",
        f"- Intimações capturadas: **{dossie.total_intimacoes}**",
        f"- Com prazo calculado: **{dossie.total_com_prazo}**",
        f"- Vencendo em até {radar.JANELA_DIAS} dias: **{dossie.total_em_alerta}**",
        "",
        "| Processo | Tribunal | Comunicação | Publicação | Prazo fatal | Dias | Nível |",
        "|---|---|---|---|---|---|---|",
    ]
    for linha in dossie.linhas:
        linhas.append(
            "| {} | {} | {} | {} | {} | {} | {} |".format(
                _celula(linha.numero_processo),
                _celula(linha.tribunal),
                _celula(linha.tipo_comunicacao),
                _celula(linha.data_publicacao),
                _celula(linha.data_fatal),
                _celula(linha.dias_para_vencer),
                _celula(linha.nivel),
            )
        )
    linhas += [
        "",
        "Fonte: DJEN (Diário de Justiça Eletrônico Nacional, CNJ), captura por API "
        "oficial. Os prazos acima são calculados por código determinístico — "
        "contagem em dias úteis, feriados e suspensões — e não por IA.",
    ]
    return "\n".join(linhas) + "\n"
