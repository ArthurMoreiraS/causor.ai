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
from app.capture.enrich import backfill_enrichment
from app.capture.poll import PollResult, poll_oab
from app.capture.scheduler import run_capture_for_oab_resilient, select_due
from app.connectors.pje.simulator import serve as serve_pje_simulator
from app.prazo_engine.calendar import ForensicCalendar
from app.prazo_engine.factory import build_calendar
from app.queue.jobs import fail_stale_running_jobs
from app.settings import settings
from app.sor import models
from app.sor.db import SessionLocal


def _yaml_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return str(value)


def _write_coverage_yaml(path: str, rows: list[dict]) -> None:
    """Escreve a matriz de cobertura em YAML determinístico (sem dependência).

    Apenas status público-seguro; evidência de validação fica no banco."""
    from pathlib import Path

    lines = ["# Matriz de cobertura de conectores (gerada por export-connector-coverage).", ""]
    for row in rows:
        first = True
        for key, value in row.items():
            prefix = "- " if first else "  "
            lines.append(f"{prefix}{key}: {_yaml_scalar(value)}")
            first = False
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


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

    provision = sub.add_parser(
        "provision-pilot",
        help="Create or update a pilot office/user for Supabase-auth onboarding",
    )
    provision.add_argument("--escritorio", required=True, help="Office name")
    provision.add_argument("--nome", required=True, help="Lawyer/user name")
    provision.add_argument("--email", required=True, help="Supabase Auth email")
    provision.add_argument("--oab", help="Main OAB number")
    provision.add_argument("--uf", help="Main OAB state")

    monitor = sub.add_parser("monitor-oab", help="Register an OAB for scheduled capture")
    monitor.add_argument("--oab", required=True)
    monitor.add_argument("--uf", required=True)
    monitor.add_argument("--escritorio", required=True, type=int)
    monitor.add_argument("--intervalo-horas", type=int, default=12)

    capture_due = sub.add_parser("capture-due", help="Run capture for all due monitored OABs")
    capture_due.add_argument(
        "--max-attempts",
        type=int,
        default=settings.capture_retry_attempts,
        help="Maximum attempts for transient HTTP/database failures",
    )
    capture_due.add_argument(
        "--backoff-seconds",
        type=float,
        default=settings.capture_retry_backoff_seconds,
        help="Initial exponential retry delay",
    )

    pje_simulator = sub.add_parser(
        "pje-simulator",
        help="Run a local fake PJe page for connector testing without tribunal access",
    )
    pje_simulator.add_argument("--host", default="127.0.0.1")
    pje_simulator.add_argument("--port", type=int, default=8765)

    enrich_processos = sub.add_parser(
        "enrich-processos",
        help="Backfill DataJud enrichment (classe/orgao/sistema/andamentos) for processos "
        "captured before enrich-on-capture was enabled",
    )
    enrich_processos.add_argument(
        "--escritorio", type=int, help="Limit to one escritorio (default: all)"
    )
    enrich_processos.add_argument(
        "--delay-seconds",
        type=float,
        default=0.5,
        help="Pause between DataJud calls to avoid tripping its rate limit on bulk backfills",
    )

    autos_due = sub.add_parser(
        "process-autos-due",
        help="Drain queued process_document jobs (extraction/OCR of captured autos)",
    )
    autos_due.add_argument(
        "--max-attempts",
        type=int,
        default=settings.document_processing_attempts,
        help="Maximum attempts for transient failures per job",
    )
    autos_due.add_argument(
        "--backoff-seconds",
        type=float,
        default=1.0,
        help="Initial exponential retry delay",
    )

    export_coverage = sub.add_parser(
        "export-connector-coverage",
        help="Export the connector coverage matrix (public-safe status) to YAML",
    )
    export_coverage.add_argument(
        "--output", required=True, help="Path to write the coverage YAML"
    )

    worker = sub.add_parser(
        "worker",
        help="Run the background job worker (drains queued captura_oab jobs)",
    )
    worker.add_argument(
        "--batch-days",
        type=int,
        default=settings.capture_batch_days,
        help="Window size (days) for progressive commit within a capture job",
    )
    worker.add_argument(
        "--idle-seconds",
        type=float,
        default=2.0,
        help="Sleep between polls when no jobs are queued",
    )
    worker.add_argument(
        "--once",
        action="store_true",
        help="Drain queued jobs once and exit (no idle loop)",
    )
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
                enrich=False,  # captura rapida; enriquecimento on-demand na minuta
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

    if args.command == "process-autos-due":
        from app.autos.worker import (
            process_due_documents,
            process_due_mni_captures,
            process_due_purges,
        )

        mni = process_due_mni_captures(SessionLocal)
        processed = process_due_documents(
            SessionLocal,
            max_attempts=args.max_attempts,
            backoff_seconds=args.backoff_seconds,
        )
        purged = process_due_purges(SessionLocal)
        print(
            f"process-autos-due: {mni} captura(s) MNI, {processed} extração(ões), "
            f"{purged} purge(s)."
        )
        return 0

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

    if args.command == "provision-pilot":
        session = SessionLocal()
        try:
            usuario = session.scalar(
                select(models.Usuario).where(models.Usuario.email == args.email)
            )
            if usuario is not None:
                escritorio = session.get(models.Escritorio, usuario.escritorio_id)
                if escritorio is not None:
                    escritorio.nome = args.escritorio
                usuario.nome = args.nome
                usuario.oab = args.oab
                usuario.oab_uf = args.uf.upper() if args.uf else None
            else:
                escritorio = session.scalar(
                    select(models.Escritorio).where(models.Escritorio.nome == args.escritorio)
                )
                if escritorio is None:
                    escritorio = models.Escritorio(nome=args.escritorio)
                    session.add(escritorio)
                    session.flush()
                usuario = models.Usuario(
                    escritorio_id=escritorio.id,
                    nome=args.nome,
                    email=args.email,
                    oab=args.oab,
                    oab_uf=args.uf.upper() if args.uf else None,
                )
                session.add(usuario)
            session.commit()
            session.refresh(usuario)
            escritorio_id = usuario.escritorio_id
            usuario_id = usuario.id
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        print(
            f"Piloto provisionado: escritorio {escritorio_id}, "
            f"usuario {usuario_id} ({args.email})."
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
        failures = 0
        try:
            stale = fail_stale_running_jobs(
                session,
                older_than_minutes=settings.job_stale_minutes,
            )
            if stale:
                session.commit()
                print(f"{len(stale)} job(s) interrompido(s) marcado(s) como failed.")
            due = select_due(session)
            print(f"{len(due)} OAB(s) para capturar.")
            for oab in due:
                label = f"{oab.oab}/{oab.uf}"
                result = run_capture_for_oab_resilient(
                    session,
                    oab,
                    djen=djen,
                    datajud=datajud,
                    calendar=calendar,
                    max_attempts=args.max_attempts,
                    backoff_seconds=args.backoff_seconds,
                )
                if result.succeeded:
                    print(
                        f"  OAB {label}: job {result.job.id} completed "
                        f"em {result.attempts} tentativa(s) -> {result.job.resultado}"
                    )
                else:
                    failures += 1
                    print(
                        f"  OAB {label}: FALHA apos {result.attempts} tentativa(s): "
                        f"{result.job.erro}"
                    )
        finally:
            session.close()
        return 1 if failures else 0
    if args.command == "export-connector-coverage":
        from app.connectors.coverage import coverage_status, known_profiles

        session = SessionLocal()
        try:
            rows = []
            for profile in known_profiles():
                status = coverage_status(session, profile=profile)
                rows.append(
                    {
                        "profile_key": profile.key,
                        "sistema": profile.sistema,
                        "tribunal": profile.tribunal,
                        "degree": profile.grau,
                        "read_autos": profile.capabilities.read_autos,
                        "prepare_filing": profile.capabilities.prepare_filing,
                        "submit_filing": profile.capabilities.submit_filing,
                        "state": status.state,
                        "last_live_validation": (
                            status.last_validation_at.isoformat()
                            if status.last_validation_at
                            else None
                        ),
                    }
                )
        finally:
            session.close()
        rows.sort(key=lambda item: item["profile_key"])
        _write_coverage_yaml(args.output, rows)
        print(f"Cobertura exportada: {len(rows)} perfil(is) -> {args.output}")
    if args.command == "enrich-processos":
        session = SessionLocal()
        try:
            result = backfill_enrichment(
                session,
                datajud=DatajudClient(),
                escritorio_id=args.escritorio,
                delay_seconds=args.delay_seconds,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        print(
            f"Enriquecimento concluído: {result.total} processo(s) sem sistema, "
            f"{result.enriquecidos} enriquecido(s), {result.sem_dados} sem dados no DataJud, "
            f"{result.sem_tribunal} sem tribunal cadastrado, {result.falhas} falha(s) HTTP."
        )
        return 0
    if args.command == "pje-simulator":
        serve_pje_simulator(host=args.host, port=args.port)
        return 0
    if args.command == "worker":
        from app.queue.worker import default_clients, run_loop, run_once

        def commit_each(s):
            s.commit()

        if args.once:
            n = run_once(
                SessionLocal,
                clients=default_clients(),
                batch_days=args.batch_days,
                commit_each=commit_each,
            )
            print(f"Worker processou {n} job(s).")
            return 0
        run_loop(
            SessionLocal,
            batch_days=args.batch_days,
            commit_each=commit_each,
            idle_seconds=args.idle_seconds,
        )
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
