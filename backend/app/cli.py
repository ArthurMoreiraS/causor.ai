"""CLI entrypoint for a capture poll cycle.

Usage:
    python -m app.cli poll --oab 12345 --uf SP --escritorio 1

Wires the real DJEN/DataJud clients and a SOR session, then delegates to
``poll_oab``. Kept thin so the orchestration stays unit-tested.
"""

from __future__ import annotations

import argparse
from datetime import date

from app.capture.datajud import DatajudClient
from app.capture.djen import DjenClient
from app.capture.poll import PollResult, poll_oab
from app.prazo_engine.calendar import ForensicCalendar
from app.prazo_engine.factory import build_calendar
from app.sor.db import SessionLocal


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
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
