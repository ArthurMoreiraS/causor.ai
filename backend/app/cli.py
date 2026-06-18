"""CLI entrypoint for a capture poll cycle.

Usage:
    python -m app.cli poll --oab 12345 --uf SP --escritorio 1

Wires the real DJEN/DataJud clients and a SOR session, then delegates to
``poll_oab``. Kept thin so the orchestration stays unit-tested.
"""

from __future__ import annotations

import argparse
from datetime import date

from sqlalchemy import select

from app.capture.datajud import DatajudClient
from app.capture.djen import DjenClient
from app.capture.poll import PollResult, poll_oab
from app.capture.scheduler import run_capture_for_oab, select_due
from app.connectors.pje.simulator import serve as serve_pje_simulator
from app.connectors.pje.session_capture import capture_pje_storage_state
from app.prazo_engine.calendar import ForensicCalendar
from app.prazo_engine.factory import build_calendar
from app.queue.jobs import create_job, mark_failed
from app.sor import models
from app.sor.db import SessionLocal
from app.vault.service import store_pje_session_reference


def default_calendar(today: date | None = None) -> ForensicCalendar:
    """Calendar spanning the previous, current and next year for safe counting."""
    year = (today or date.today()).year
    return build_calendar([year - 1, year, year + 1])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="causor", description="Causor capture CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    poll = sub.add_parser("poll", help="Run one capture poll cycle for an OAB")
    poll.add_argument("--oab", required=True)
    poll.add_argument("--uf", required=True)
    poll.add_argument("--escritorio", required=True, type=int)
    poll.add_argument("--dias", type=int, default=15, help="Provisional deadline length")

    sub.add_parser("seed-demo", help="Create/refresh the idempotent demo dataset")

    monitor = sub.add_parser("monitor-oab", help="Register an OAB for scheduled capture")
    monitor.add_argument("--oab", required=True)
    monitor.add_argument("--uf", required=True)
    monitor.add_argument("--escritorio", required=True, type=int)
    monitor.add_argument("--intervalo-horas", type=int, default=12)

    sub.add_parser("capture-due", help="Run capture for all due monitored OABs")

    pje_session = sub.add_parser(
        "pje-capture-session",
        help="Open PJe for human login and store the Playwright session in the vault",
    )
    pje_session.add_argument("--usuario", required=True, type=int)
    pje_session.add_argument("--tribunal", required=True)
    pje_session.add_argument("--url-base", required=True)
    pje_session.add_argument(
        "--assinatura-modo",
        choices=["manual_pjeoffice", "cloud_certificate"],
        default="manual_pjeoffice",
    )
    pje_session.add_argument("--timeout-seconds", type=int, default=300)
    pje_session.add_argument("--headless", action="store_true")

    pje_simulator = sub.add_parser(
        "pje-simulator",
        help="Run a local fake PJe page for connector testing without tribunal access",
    )
    pje_simulator.add_argument("--host", default="127.0.0.1")
    pje_simulator.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "poll":
        session = SessionLocal()
        try:
            result: PollResult = poll_oab(
                session,
                oab=args.oab,
                uf=args.uf,
                escritorio_id=args.escritorio,
                djen=DjenClient(),
                datajud=DatajudClient(),
                calendar=default_calendar(),
                dias_default=args.dias,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        print(
            f"Poll concluído: {result.intimacoes_novas} novas intimações, "
            f"{result.processos_enriquecidos} processos enriquecidos, "
            f"{result.prazos_registrados} prazos registrados."
        )

    if args.command == "seed-demo":
        from app.sor.seed_demo import seed_demo

        session = SessionLocal()
        try:
            seed = seed_demo(session)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        print(
            f"Seed de demo aplicada (escritório {seed.escritorio_id}): "
            f"{seed.processos} processos, {seed.intimacoes} intimações, "
            f"{seed.prazos} prazos, {seed.peticoes} petições."
        )

    if args.command == "monitor-oab":
        session = SessionLocal()
        try:
            oab = session.scalar(
                select(models.OabMonitorada).where(
                    models.OabMonitorada.escritorio_id == args.escritorio,
                    models.OabMonitorada.oab == args.oab,
                    models.OabMonitorada.uf == args.uf,
                )
            )
            if oab is None:
                oab = models.OabMonitorada(
                    escritorio_id=args.escritorio,
                    oab=args.oab,
                    uf=args.uf,
                    intervalo_horas=args.intervalo_horas,
                    ativo=True,
                )
                session.add(oab)
            else:
                oab.ativo = True
                oab.intervalo_horas = args.intervalo_horas
            session.commit()
            session.refresh(oab)
            label = f"{oab.oab}/{oab.uf}"
            oab_id = oab.id
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        print(f"OAB monitorada {label} (id {oab_id}) ativa.")

    if args.command == "capture-due":
        djen = DjenClient()
        datajud = DatajudClient()
        calendar = default_calendar()
        session = SessionLocal()
        try:
            due = select_due(session)
            print(f"{len(due)} OAB(s) para capturar.")
            for oab in due:
                oab_id, label = oab.id, f"{oab.oab}/{oab.uf}"
                oab_str, uf_str, esc_id = oab.oab, oab.uf, oab.escritorio_id
                try:
                    job = run_capture_for_oab(
                        session, oab, djen=djen, datajud=datajud, calendar=calendar
                    )
                    session.commit()
                    print(f"  OAB {label}: job {job.id} {job.status} -> {job.resultado}")
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    job = create_job(
                        session,
                        tipo="captura_oab",
                        entidade="oab_monitorada",
                        entidade_id=oab_id,
                        payload={"oab": oab_str, "uf": uf_str, "escritorio_id": esc_id},
                    )
                    mark_failed(session, job, str(exc))
                    session.commit()
                    print(f"  OAB {label}: FALHA {exc}")
        finally:
            session.close()
    if args.command == "pje-capture-session":
        storage_state = capture_pje_storage_state(
            base_url=args.url_base,
            timeout_seconds=args.timeout_seconds,
            headless=args.headless,
        )
        session = SessionLocal()
        try:
            credencial = store_pje_session_reference(
                session,
                usuario_id=args.usuario,
                tribunal=args.tribunal,
                url_base=args.url_base,
                storage_state=storage_state,
                signature_mode=args.assinatura_modo,
            )
            session.commit()
            session.refresh(credencial)
            credencial_id = credencial.id
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        print(f"Sessao PJe cadastrada como credencial {credencial_id}.")
    if args.command == "pje-simulator":
        serve_pje_simulator(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
