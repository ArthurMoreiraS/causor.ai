"""Tests for the CLI wiring (without hitting the network)."""

from datetime import date

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


def test_parser_accepts_pje_capture_session():
    parser = _build_parser()
    args = parser.parse_args(
        [
            "pje-capture-session",
            "--usuario",
            "7",
            "--tribunal",
            "TJSP",
            "--url-base",
            "https://pje-treinamento.tjsp.jus.br/pje",
        ]
    )
    assert args.command == "pje-capture-session"
    assert args.usuario == 7
    assert args.assinatura_modo == "manual_pjeoffice"


def test_cli_pje_capture_session_stores_vault_reference(db_session, monkeypatch):
    import app.cli as cli
    from app.sor import models

    esc = models.Escritorio(nome="Escritorio PJe")
    db_session.add(esc)
    db_session.flush()
    usuario = models.Usuario(escritorio_id=esc.id, nome="Adv", email="adv@example.com")
    db_session.add(usuario)
    db_session.flush()

    storage_state = {"cookies": [{"name": "JSESSIONID", "value": "secret-cookie"}]}
    monkeypatch.setattr(cli, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    monkeypatch.setattr(
        cli,
        "capture_pje_storage_state",
        lambda **kwargs: storage_state,
    )

    rc = cli.main(
        [
            "pje-capture-session",
            "--usuario",
            str(usuario.id),
            "--tribunal",
            "TJSP",
            "--url-base",
            "https://pje-treinamento.tjsp.jus.br/pje",
        ]
    )

    assert rc == 0
    credencial = db_session.query(models.CredencialAssinatura).one()
    assert credencial.provedor == "PJeSession"
    assert "secret-cookie" not in credencial.referencia_vault


def test_parser_accepts_pje_simulator():
    parser = _build_parser()
    args = parser.parse_args(["pje-simulator", "--port", "8765"])

    assert args.command == "pje-simulator"
    assert args.host == "127.0.0.1"
    assert args.port == 8765
