"""Sinal externo de completude para a captura por upload.

Numa captura de tribunal, a dupla enumeração prova completude: a lista vem de
fora. No upload (``autos/upload.py``) as duas enumerações são a mesma lista que o
advogado entregou, então ``complete`` afirma só *"recebemos exatamente estes
arquivos, íntegros"*.

Este módulo **não** transforma declaração em prova. Ele busca no DataJud — API
pública nacional, já usada na captura — quantos movimentos de juntada o tribunal
registra no processo, e compara com quantos arquivos chegaram. Movimento
processual não é peça dos autos: um movimento pode juntar várias peças e nem toda
peça gera movimento. Por isso a divergência é motivo para **perguntar ao
advogado**, nunca para reprovar a captura.

Falha do DataJud é registrada e engolida: a captura já está completa quando esta
conferência roda, e derrubar uma captura íntegra por causa de uma API de terceiro
seria trocar um problema real por um imaginário.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.capture.datajud import MovimentoDTO, ProcessoDTO
from app.sor import models

#: Chave sob a qual o resultado vive em ``CapturaAutos.evidence``.
CHAVE_EVIDENCIA = "conferencia_datajud"


class ConsultaDatajud(Protocol):
    def consultar_processo(
        self, numero_processo: str, *, tribunal: str
    ) -> ProcessoDTO | None: ...


@dataclass(frozen=True)
class ConferenciaDatajud:
    consultado: bool
    movimentos: int
    juntadas: int
    arquivos_recebidos: int
    divergencia: bool
    motivo: str | None = None


def _sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFD", texto)
    return "".join(
        caractere
        for caractere in normalizado
        if unicodedata.category(caractere) != "Mn"
    ).lower()


def contar_juntadas(movimentos: Iterable[MovimentoDTO]) -> int:
    """Movimentos cujo nome menciona juntada — a redação padrão da TPU/CNJ."""
    return sum(
        1
        for movimento in movimentos
        if movimento.nome and "juntada" in _sem_acento(movimento.nome)
    )


def conferir_upload_com_datajud(
    session: Session,
    *,
    capture: models.CapturaAutos,
    processo: models.Processo,
    arquivos_recebidos: int,
    datajud: ConsultaDatajud,
) -> ConferenciaDatajud:
    """Compara os arquivos entregues com as juntadas que o tribunal registra."""
    resultado = _conferir(
        processo=processo, arquivos_recebidos=arquivos_recebidos, datajud=datajud
    )
    capture.evidence = {**(capture.evidence or {}), CHAVE_EVIDENCIA: asdict(resultado)}
    session.flush()
    return resultado


def _conferir(
    *,
    processo: models.Processo,
    arquivos_recebidos: int,
    datajud: ConsultaDatajud,
) -> ConferenciaDatajud:
    def _nao_consultado(motivo: str) -> ConferenciaDatajud:
        return ConferenciaDatajud(
            consultado=False,
            movimentos=0,
            juntadas=0,
            arquivos_recebidos=arquivos_recebidos,
            divergencia=False,
            motivo=motivo,
        )

    if not processo.tribunal:
        return _nao_consultado("sem_tribunal")

    try:
        dto = datajud.consultar_processo(processo.numero, tribunal=processo.tribunal)
    except Exception:  # noqa: BLE001 — API de terceiro não derruba captura íntegra
        return _nao_consultado("erro_na_consulta")

    if dto is None:
        return _nao_consultado("processo_nao_encontrado")

    juntadas = contar_juntadas(dto.movimentos)
    return ConferenciaDatajud(
        consultado=True,
        movimentos=len(dto.movimentos),
        juntadas=juntadas,
        arquivos_recebidos=arquivos_recebidos,
        divergencia=juntadas > arquivos_recebidos,
    )
