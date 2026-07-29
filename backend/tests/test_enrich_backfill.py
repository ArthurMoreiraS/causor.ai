"""TDD for the enrichment backfill service (shell processos -> DataJud)."""

import httpx

from app.capture.datajud import ProcessoDTO
from app.capture.enrich import backfill_enrichment, backfill_sistema
from app.sor import models


class FakeDatajud:
    def __init__(self, by_numero=None, *, sistema="pje"):
        self._by_numero = by_numero
        self._sistema = sistema
        self.calls = []

    def consultar_processo(self, numero_processo, *, tribunal):
        self.calls.append(numero_processo)
        if self._by_numero is not None:
            return self._by_numero.get(numero_processo)
        return ProcessoDTO(numero_processo=numero_processo, sistema=self._sistema)


def _escritorio(db_session, nome="Escritorio"):
    esc = models.Escritorio(nome=nome)
    db_session.add(esc)
    db_session.flush()
    return esc


def test_backfill_enriches_only_processos_without_classe(db_session):
    esc = _escritorio(db_session)
    # "shell": sem classe (não passou pelo DataJud) — o sistema já vem da captura.
    shell = models.Processo(
        escritorio_id=esc.id, numero="00000010020248260100", tribunal="TJSP", sistema="e-SAJ"
    )
    # já enriquecido pelo DataJud (tem classe) — deve ser pulado.
    ja = models.Processo(
        escritorio_id=esc.id, numero="00000020020248260100", tribunal="TJSP",
        sistema="PJe", classe="Procedimento Comum",
    )
    sem_tribunal = models.Processo(escritorio_id=esc.id, numero="00000030020248260100", tribunal=None)
    db_session.add_all([shell, ja, sem_tribunal])
    db_session.flush()

    datajud = FakeDatajud()
    result = backfill_enrichment(db_session, datajud=datajud, escritorio_id=esc.id, delay_seconds=0)

    # só o shell (sem classe, com tribunal) foi consultado; o com classe foi pulado
    assert datajud.calls == ["00000010020248260100"]
    assert result.enriquecidos == 1
    assert result.sem_tribunal == 1
    db_session.flush()  # serviço deixa o commit/flush pro chamador (CLI/background)
    db_session.refresh(shell)
    assert shell.sistema == "PJe"  # normalizado: DataJud manda "pje", gravamos canonico


def test_backfill_sistema_fills_from_tribunal_offline(db_session):
    esc = _escritorio(db_session, nome="Sistema")
    tjsp = models.Processo(escritorio_id=esc.id, numero="00000010020248260100", tribunal="TJSP")
    trt = models.Processo(escritorio_id=esc.id, numero="00000020020248260100", tribunal="TRT2")
    sem_trib = models.Processo(escritorio_id=esc.id, numero="00000030020248260100", tribunal=None)
    ja = models.Processo(
        escritorio_id=esc.id, numero="00000040020248260100", tribunal="TJSP", sistema="PJe"
    )
    db_session.add_all([tjsp, trt, sem_trib, ja])
    db_session.flush()

    preenchidos = backfill_sistema(db_session, escritorio_id=esc.id)

    assert preenchidos == 2  # tjsp e trt; sem_trib e ja não contam
    db_session.flush()
    for p in (tjsp, trt, sem_trib, ja):
        db_session.refresh(p)
    assert tjsp.sistema == "e-SAJ"
    assert trt.sistema == "PJe"
    assert sem_trib.sistema is None  # sem tribunal, não dá pra inferir
    assert ja.sistema == "PJe"  # já tinha, não é tocado


def test_backfill_tolerates_datajud_failure(db_session):
    esc = _escritorio(db_session, nome="Falha")
    shell = models.Processo(escritorio_id=esc.id, numero="00000010020248260100", tribunal="TJSP")
    db_session.add(shell)
    db_session.flush()

    class FailingDatajud:
        def consultar_processo(self, numero_processo, *, tribunal):
            request = httpx.Request("POST", "https://datajud.example")
            raise httpx.ConnectError("offline", request=request)

    result = backfill_enrichment(db_session, datajud=FailingDatajud(), escritorio_id=esc.id, delay_seconds=0)

    assert result.falhas == 1
    assert result.enriquecidos == 0
    db_session.refresh(shell)
    assert shell.sistema is None  # inalterado, não trava


def test_backfill_respects_limit(db_session):
    esc = _escritorio(db_session, nome="Limite")
    for n in range(3):
        db_session.add(
            models.Processo(escritorio_id=esc.id, numero=f"0000{n}010020248260100", tribunal="TJSP")
        )
    db_session.flush()

    datajud = FakeDatajud()
    result = backfill_enrichment(
        db_session, datajud=datajud, escritorio_id=esc.id, limit=2, delay_seconds=0
    )

    assert len(datajud.calls) == 2
    assert result.enriquecidos == 2
