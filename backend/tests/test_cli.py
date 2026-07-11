"""Tests for the CLI wiring (without hitting the network)."""

from datetime import date

import pytest

from app.cli import _build_parser, default_calendar


def test_parser_requires_subcommand():
    parser = _build_parser()
    args = parser.parse_args(["poll", "--oab", "12345", "--uf", "SP", "--escritorio", "1"])
    assert args.command == "poll"
    assert args.oab == "12345"
    assert args.escritorio == 1
    assert args.dias == 15


def test_default_calendar_spans_three_years():
    cal = default_calendar(today=date(2024, 6, 1))
    # National holiday in the prior and next year should be recognized.
    assert not cal.is_business_day(date(2023, 12, 25))
    assert not cal.is_business_day(date(2025, 12, 25))


def test_cli_monitor_oab_registers(db_session, monkeypatch):
    import app.cli as cli
    from app.sor import models

    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()

    monkeypatch.setattr(cli, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    rc = cli.main(["monitor-oab", "--oab", "12345", "--uf", "SP", "--escritorio", str(esc.id)])
    assert rc == 0
    oab = db_session.query(models.OabMonitorada).one()
    assert oab.oab == "12345"
    assert oab.ativo is True


def test_cli_provision_pilot_is_idempotent(db_session, monkeypatch):
    import app.cli as cli
    from app.sor import models

    monkeypatch.setattr(cli, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    args = [
        "provision-pilot",
        "--escritorio",
        "Teste Advocacia",
        "--nome",
        "Ana Teste",
        "--email",
        "ana@example.com",
        "--oab",
        "12345",
        "--uf",
        "sp",
    ]
    assert cli.main(args) == 0
    assert cli.main(args) == 0

    usuario = db_session.query(models.Usuario).one()
    escritorio = db_session.query(models.Escritorio).one()
    assert usuario.email == "ana@example.com"
    assert usuario.oab_uf == "SP"
    assert usuario.escritorio_id == escritorio.id


def test_cli_capture_due_runs(db_session, monkeypatch):
    import app.cli as cli
    from app.capture.djen import ComunicacaoDTO
    from app.sor import models

    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()
    db_session.add(models.OabMonitorada(escritorio_id=esc.id, oab="12345", uf="SP"))
    db_session.flush()

    class FakeDjen:
        def consultar(self, oab, uf, **kw):
            return [
                ComunicacaoDTO.from_item(
                    {
                        "id": "111",
                        "numero_processo": "0000001-00.2024.8.26.0100",
                        "siglaTribunal": "TJSP",
                        "tipoComunicacao": "Intimação",
                        "texto": "Manifestar em 15 dias.",
                        "data_disponibilizacao": "2024-09-06",
                    }
                )
            ]

    class FakeDatajud:
        def consultar_processo(self, numero_processo, *, tribunal):
            return None

    monkeypatch.setattr(cli, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    monkeypatch.setattr(cli, "DjenClient", lambda: FakeDjen())
    monkeypatch.setattr(cli, "DatajudClient", lambda: FakeDatajud())

    rc = cli.main(["capture-due"])
    assert rc == 0
    assert db_session.query(models.Intimacao).count() == 1
    job = db_session.query(models.JobExecucao).filter_by(tipo="captura_oab").one()
    assert job.status == "completed"


def test_cli_capture_due_accepts_partial_when_djen_down(db_session, monkeypatch):
    """DJEN sempre fora: scheduler aceita parcial (djen_indisponivel=True),
    rc=0, job completed com flag de indisponibilidade."""
    import httpx

    import app.cli as cli
    from app.sor import models

    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()
    db_session.add(models.OabMonitorada(escritorio_id=esc.id, oab="12345", uf="SP"))
    db_session.commit()

    class FailingDjen:
        def consultar(self, oab, uf, **kw):
            request = httpx.Request("GET", "https://comunica.example")
            raise httpx.ConnectError("offline", request=request)

    monkeypatch.setattr(cli, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    monkeypatch.setattr(cli, "DjenClient", lambda: FailingDjen())

    class _NoopDatajud:
        def consultar_processo(self, *a, **kw):
            return None

    monkeypatch.setattr(cli, "DatajudClient", lambda: _NoopDatajud())

    rc = cli.main(["capture-due", "--max-attempts", "2", "--backoff-seconds", "0"])

    assert rc == 0
    job = db_session.query(models.JobExecucao).filter_by(tipo="captura_oab").one()
    assert job.status == "completed"
    assert job.resultado.get("djen_indisponivel") is True


def test_parser_rejects_removed_pje_capture_session():
    # A sessão de tribunal vive no agente local; o comando de captura via
    # backend foi removido junto com o vault de sessão.
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["pje-capture-session", "--usuario", "7"])


def test_cli_enrich_processos_backfills_only_unenriched(db_session, monkeypatch):
    import app.cli as cli
    from app.capture.datajud import ProcessoDTO
    from app.sor import models

    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()

    # numero fica sempre na forma canonica (so digitos, ver canonical_numero)
    sem_sistema = models.Processo(
        escritorio_id=esc.id, numero="00000010020248260100", tribunal="TJSP"
    )
    ja_enriquecido = models.Processo(
        escritorio_id=esc.id,
        numero="00000020020248260100",
        tribunal="TJSP",
        sistema="pje",
        classe="Procedimento Comum",  # já enriquecido pelo DataJud -> pulado
    )
    sem_tribunal = models.Processo(
        escritorio_id=esc.id, numero="00000030020248260100", tribunal=None
    )
    db_session.add_all([sem_sistema, ja_enriquecido, sem_tribunal])
    db_session.flush()

    consultados: list[str] = []

    class FakeDatajud:
        def consultar_processo(self, numero_processo, *, tribunal):
            consultados.append(numero_processo)
            return ProcessoDTO(numero_processo=numero_processo, sistema="pje")

    monkeypatch.setattr(cli, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    monkeypatch.setattr(cli, "DatajudClient", lambda: FakeDatajud())

    rc = cli.main(["enrich-processos", "--delay-seconds", "0"])

    assert rc == 0
    # so o processo sem sistema (e com tribunal) foi consultado no DataJud
    assert consultados == ["00000010020248260100"]
    db_session.refresh(sem_sistema)
    assert sem_sistema.sistema == "pje"
    db_session.refresh(ja_enriquecido)
    assert ja_enriquecido.sistema == "pje"  # inalterado, ja tinha valor
    db_session.refresh(sem_tribunal)
    assert sem_tribunal.sistema is None  # pulado, sem tribunal pra consultar


def test_cli_enrich_processos_tolerates_datajud_failure(db_session, monkeypatch):
    import httpx

    import app.cli as cli
    from app.sor import models

    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()
    processo = models.Processo(
        escritorio_id=esc.id, numero="00000010020248260100", tribunal="TJSP"
    )
    db_session.add(processo)
    db_session.flush()

    class FailingDatajud:
        def consultar_processo(self, numero_processo, *, tribunal):
            request = httpx.Request("POST", "https://datajud.example")
            raise httpx.ConnectError("offline", request=request)

    monkeypatch.setattr(cli, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    monkeypatch.setattr(cli, "DatajudClient", lambda: FailingDatajud())

    rc = cli.main(["enrich-processos", "--delay-seconds", "0"])

    assert rc == 0  # uma falha isolada nao derruba o comando
    db_session.refresh(processo)
    assert processo.sistema is None


def test_parser_accepts_pje_simulator():
    parser = _build_parser()
    args = parser.parse_args(["pje-simulator", "--port", "8765"])

    assert args.command == "pje-simulator"
    assert args.host == "127.0.0.1"
    assert args.port == 8765
