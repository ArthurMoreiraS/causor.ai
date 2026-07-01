# Captura Real Agendada — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ligar a captura DJEN/DataJud em produção: uma OAB monitorada é capturada de forma agendada e incremental, populando o SOR com intimações reais e prazos provisórios — sem depender de escritório-piloto nem de provedor de assinatura.

**Architecture:** Reusa o `poll_oab` já testado. Acrescenta (1) a entidade `OabMonitorada` que diz quais OABs vigiar e de quando retomar; (2) um executor de job `run_capture_oab_job` que roda `poll_oab` e grava status+auditoria no contrato `job_execucao` existente; (3) um scheduler com comando CLI `capture-due` disparado por cron/Agendador do Windows. O contrato de job fica intacto, então um worker Redis/RQ entra depois sem reescrever esta camada (evita o problema do RQ em dev Windows).

**Tech Stack:** Python 3.12, SQLAlchemy 2, FastAPI, Alembic, httpx, pytest (SQLite in-memory nos testes), workalendar.

---

## File Structure

- `backend/app/sor/models.py` — **Modify**: novo modelo `OabMonitorada`.
- `backend/alembic/versions/d3b1c0f5a9e2_add_oab_monitorada.py` — **Create**: migration da tabela.
- `backend/app/settings.py` — **Modify**: knobs `capture_lookback_days`, `capture_intervalo_horas_default`.
- `backend/app/queue/jobs.py` — **Modify**: executor `run_capture_oab_job`.
- `backend/app/capture/scheduler.py` — **Create**: `select_due`, `run_capture_for_oab`.
- `backend/app/cli.py` — **Modify**: comandos `monitor-oab` e `capture-due`.
- `backend/app/api/schemas.py` — **Modify**: `OabMonitoradaOut`, `OabMonitoradaCreate`.
- `backend/app/api/main.py` — **Modify**: `GET/POST /capturas/oab`.
- `backend/tests/test_oab_monitorada_model.py` — **Create**.
- `backend/tests/test_run_capture_job.py` — **Create**.
- `backend/tests/test_capture_scheduler.py` — **Create**.
- `backend/tests/test_cli.py` — **Modify**: cobre `monitor-oab` e `capture-due`.
- `backend/tests/test_api.py` — **Modify**: cobre `/capturas/oab`.

Todos os comandos rodam de `backend/` com `./.venv/Scripts/python.exe`.

---

### Task 1: Modelo `OabMonitorada` + migration

**Files:**
- Modify: `backend/app/sor/models.py` (após `Usuario`, antes de `Cliente`)
- Create: `backend/alembic/versions/d3b1c0f5a9e2_add_oab_monitorada.py`
- Test: `backend/tests/test_oab_monitorada_model.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_oab_monitorada_model.py
"""TDD for the OabMonitorada SOR model."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.sor import models


@pytest.fixture
def escritorio(db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()
    return esc


def test_defaults_ativo_and_intervalo(db_session, escritorio):
    oab = models.OabMonitorada(escritorio_id=escritorio.id, oab="12345", uf="SP")
    db_session.add(oab)
    db_session.flush()

    assert oab.id is not None
    assert oab.ativo is True
    assert oab.intervalo_horas == 12
    assert oab.ultima_captura_em is None
    assert oab.cursor_data is None


def test_unique_per_escritorio_oab_uf(db_session, escritorio):
    db_session.add(models.OabMonitorada(escritorio_id=escritorio.id, oab="12345", uf="SP"))
    db_session.flush()
    db_session.add(models.OabMonitorada(escritorio_id=escritorio.id, oab="12345", uf="SP"))
    with pytest.raises(IntegrityError):
        db_session.flush()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_oab_monitorada_model.py -v`
Expected: FAIL com `AttributeError: module 'app.sor.models' has no attribute 'OabMonitorada'`.

- [ ] **Step 3: Add the model**

Em `backend/app/sor/models.py`, logo após a classe `Usuario` (a `relationship` não é necessária no `Escritorio`):

```python
class OabMonitorada(TimestampMixin, Base):
    """An OAB registration polled on a schedule for new intimações (DJEN)."""

    __tablename__ = "oab_monitorada"
    __table_args__ = (
        UniqueConstraint("escritorio_id", "oab", "uf", name="uq_oab_monitorada"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorio.id"), nullable=False)
    oab: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    uf: Mapped[str] = mapped_column(String(2), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    intervalo_horas: Mapped[int] = mapped_column(Integer, default=12)
    ultima_captura_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cursor_data: Mapped[date | None] = mapped_column(Date)
```

(Os imports `Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint`, `Mapped`, `mapped_column`, `date`, `datetime` já existem no topo do arquivo.)

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_oab_monitorada_model.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Create the Alembic migration**

```python
# backend/alembic/versions/d3b1c0f5a9e2_add_oab_monitorada.py
"""add oab_monitorada

Revision ID: d3b1c0f5a9e2
Revises: c2a4d9e8f013
Create Date: 2026-06-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d3b1c0f5a9e2"
down_revision: Union[str, Sequence[str], None] = "c2a4d9e8f013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "oab_monitorada",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("escritorio_id", sa.Integer(), nullable=False),
        sa.Column("oab", sa.String(length=20), nullable=False),
        sa.Column("uf", sa.String(length=2), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("intervalo_horas", sa.Integer(), nullable=False),
        sa.Column("ultima_captura_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cursor_data", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["escritorio_id"], ["escritorio.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("escritorio_id", "oab", "uf", name="uq_oab_monitorada"),
    )
    op.create_index("ix_oab_monitorada_oab", "oab_monitorada", ["oab"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_oab_monitorada_oab", table_name="oab_monitorada")
    op.drop_table("oab_monitorada")
```

- [ ] **Step 6: Verify migration applies on Postgres**

Run: `CAUSOR_DATABASE_URL=postgresql+psycopg://causor:causor@localhost:5432/causor ./.venv/Scripts/alembic.exe upgrade head`
Expected: roda sem erro e cria `oab_monitorada` (revisão `d3b1c0f5a9e2`).

- [ ] **Step 7: Commit**

```bash
git add backend/app/sor/models.py backend/alembic/versions/d3b1c0f5a9e2_add_oab_monitorada.py backend/tests/test_oab_monitorada_model.py
git commit -m "feat(capture): modelo OabMonitorada + migration"
```

---

### Task 2: Settings de agendamento

**Files:**
- Modify: `backend/app/settings.py`

- [ ] **Step 1: Add the knobs**

Em `backend/app/settings.py`, após o bloco `# HTTP`:

```python
    # Capture scheduling
    capture_lookback_days: int = 3
    capture_intervalo_horas_default: int = 12
```

- [ ] **Step 2: Verify import still works**

Run: `./.venv/Scripts/python.exe -c "from app.settings import settings; print(settings.capture_lookback_days, settings.capture_intervalo_horas_default)"`
Expected: `3 12`

- [ ] **Step 3: Commit**

```bash
git add backend/app/settings.py
git commit -m "feat(capture): config de lookback e intervalo de captura"
```

---

### Task 3: Executor de job `run_capture_oab_job`

**Files:**
- Modify: `backend/app/queue/jobs.py`
- Test: `backend/tests/test_run_capture_job.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_run_capture_job.py
"""TDD for the captura_oab job executor."""

from datetime import date

import pytest

from app.capture.djen import ComunicacaoDTO
from app.prazo_engine.factory import build_calendar
from app.queue.jobs import JobError, create_job, run_capture_oab_job
from app.sor import models


class FakeDjen:
    def __init__(self, items):
        self._items = items
        self.calls = []

    def consultar(self, oab, uf, **kw):
        self.calls.append((oab, uf, kw))
        return self._items


class FakeDatajud:
    def consultar_processo(self, numero_processo, *, tribunal):
        return None


@pytest.fixture
def calendar():
    return build_calendar([2024, 2025])


@pytest.fixture
def escritorio(db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()
    return esc


def _comunicacao(fonte_id="111"):
    return ComunicacaoDTO.from_item(
        {
            "id": fonte_id,
            "numero_processo": "0000001-00.2024.8.26.0100",
            "siglaTribunal": "TJSP",
            "tipoComunicacao": "Intimação",
            "texto": "Intimada para manifestar em 15 dias.",
            "data_disponibilizacao": "2024-09-06",
        }
    )


def test_run_capture_job_completes_and_audits(db_session, escritorio, calendar):
    job = create_job(
        db_session,
        tipo="captura_oab",
        entidade="oab_monitorada",
        entidade_id=1,
        payload={"oab": "12345", "uf": "SP", "escritorio_id": escritorio.id},
    )
    db_session.flush()

    djen = FakeDjen([_comunicacao()])
    run_capture_oab_job(
        db_session, job.id, djen=djen, datajud=FakeDatajud(), calendar=calendar
    )

    assert job.status == "completed"
    assert job.resultado["intimacoes_novas"] == 1
    assert job.resultado["prazos_registrados"] == 1
    acoes = {a.acao for a in db_session.query(models.AuditLog).all()}
    assert {"job_iniciado", "job_concluido"} <= acoes


def test_run_capture_job_rejects_wrong_type(db_session, escritorio, calendar):
    job = create_job(db_session, tipo="protocolo_peticao", entidade_id=1)
    db_session.flush()
    with pytest.raises(JobError):
        run_capture_oab_job(
            db_session, job.id, djen=FakeDjen([]), datajud=FakeDatajud(), calendar=calendar
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_run_capture_job.py -v`
Expected: FAIL com `ImportError: cannot import name 'run_capture_oab_job'`.

- [ ] **Step 3: Implement the executor**

Em `backend/app/queue/jobs.py`: trocar o import de data por `from datetime import date, datetime, timezone` e adicionar, após os imports, `from app.capture.poll import poll_oab`. Acrescentar a função (após `get_job`):

```python
def run_capture_oab_job(
    session: Session,
    job_id: int,
    *,
    djen,
    datajud,
    calendar,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    dias_default: int = 15,
) -> models.JobExecucao:
    """Execute a queued captura_oab job: run poll_oab and record status + audit.

    Não captura exceções de domínio: o chamador (scheduler) faz rollback do estado
    parcial de captura e registra a falha numa transação limpa.
    """
    job = get_job(session, job_id)
    if job.tipo != "captura_oab":
        raise JobError(f"job {job_id} nao e de captura (tipo={job.tipo})")

    payload = job.payload or {}
    try:
        oab = payload["oab"]
        uf = payload["uf"]
        escritorio_id = payload["escritorio_id"]
    except KeyError as exc:
        raise JobError(f"payload de captura incompleto: falta {exc}") from exc

    mark_running(session, job)
    result = poll_oab(
        session,
        oab=oab,
        uf=uf,
        escritorio_id=escritorio_id,
        djen=djen,
        datajud=datajud,
        calendar=calendar,
        dias_default=dias_default,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )
    mark_completed(
        session,
        job,
        {
            "intimacoes_novas": result.intimacoes_novas,
            "processos_enriquecidos": result.processos_enriquecidos,
            "prazos_registrados": result.prazos_registrados,
        },
    )
    return job
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_run_capture_job.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/queue/jobs.py backend/tests/test_run_capture_job.py
git commit -m "feat(capture): executor run_capture_oab_job com auditoria"
```

---

### Task 4: Scheduler `select_due` + `run_capture_for_oab`

**Files:**
- Create: `backend/app/capture/scheduler.py`
- Test: `backend/tests/test_capture_scheduler.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_capture_scheduler.py
"""TDD for the capture scheduler (select_due + run_capture_for_oab)."""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.capture.djen import ComunicacaoDTO
from app.capture.scheduler import run_capture_for_oab, select_due
from app.prazo_engine.factory import build_calendar
from app.sor import models


class FakeDjen:
    def __init__(self, items):
        self._items = items
        self.calls = []

    def consultar(self, oab, uf, **kw):
        self.calls.append((oab, uf, kw))
        return self._items


class FakeDatajud:
    def consultar_processo(self, numero_processo, *, tribunal):
        return None


@pytest.fixture
def calendar():
    return build_calendar([2024, 2025])


@pytest.fixture
def escritorio(db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()
    return esc


def _comunicacao(fonte_id="111"):
    return ComunicacaoDTO.from_item(
        {
            "id": fonte_id,
            "numero_processo": "0000001-00.2024.8.26.0100",
            "siglaTribunal": "TJSP",
            "tipoComunicacao": "Intimação",
            "texto": "Intimada para manifestar em 15 dias.",
            "data_disponibilizacao": "2024-09-06",
        }
    )


def test_select_due_includes_never_captured_and_skips_inactive(db_session, escritorio):
    nunca = models.OabMonitorada(escritorio_id=escritorio.id, oab="111", uf="SP")
    inativa = models.OabMonitorada(escritorio_id=escritorio.id, oab="222", uf="SP", ativo=False)
    recente = models.OabMonitorada(
        escritorio_id=escritorio.id, oab="333", uf="SP",
        ultima_captura_em=datetime.now(timezone.utc), intervalo_horas=12,
    )
    db_session.add_all([nunca, inativa, recente])
    db_session.flush()

    due = select_due(db_session)
    oabs = {o.oab for o in due}
    assert "111" in oabs
    assert "222" not in oabs
    assert "333" not in oabs


def test_select_due_includes_overdue(db_session, escritorio):
    velha = models.OabMonitorada(
        escritorio_id=escritorio.id, oab="444", uf="SP",
        ultima_captura_em=datetime.now(timezone.utc) - timedelta(hours=24),
        intervalo_horas=12,
    )
    db_session.add(velha)
    db_session.flush()
    assert {o.oab for o in select_due(db_session)} == {"444"}


def test_run_capture_for_oab_advances_cursor_and_captures(db_session, escritorio, calendar):
    oab = models.OabMonitorada(escritorio_id=escritorio.id, oab="12345", uf="SP")
    db_session.add(oab)
    db_session.flush()

    today = date(2024, 9, 10)
    djen = FakeDjen([_comunicacao()])
    job = run_capture_for_oab(
        db_session, oab, djen=djen, datajud=FakeDatajud(), calendar=calendar, today=today
    )

    assert job.status == "completed"
    assert oab.cursor_data == today
    assert oab.ultima_captura_em is not None
    # janela incremental: data_inicio = today - lookback (3 dias) por não haver cursor
    _, _, kw = djen.calls[0]
    assert kw["data_inicio"] == date(2024, 9, 7)
    assert kw["data_fim"] == today
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_capture_scheduler.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.capture.scheduler'`.

- [ ] **Step 3: Implement the scheduler**

```python
# backend/app/capture/scheduler.py
"""Schedule and run capture cycles for monitored OAB registrations.

Windows-friendly: o comando CLI ``capture-due`` (cron / Agendador de Tarefas)
dispara o executor in-process. O contrato de job não muda, então um worker
Redis/RQ pode substituir o executor depois sem tocar nesta camada.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.capture.datajud import DatajudClient
from app.capture.djen import DjenClient
from app.prazo_engine.calendar import ForensicCalendar
from app.queue.jobs import create_job, run_capture_oab_job
from app.settings import settings
from app.sor import models


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def select_due(session: Session, *, now: datetime | None = None) -> list[models.OabMonitorada]:
    """Active monitored OABs whose last capture is older than their interval."""
    now = now or _utcnow()
    stmt = select(models.OabMonitorada).where(models.OabMonitorada.ativo.is_(True))
    due: list[models.OabMonitorada] = []
    for oab in session.scalars(stmt):
        if oab.ultima_captura_em is None:
            due.append(oab)
            continue
        proxima = _as_aware(oab.ultima_captura_em) + timedelta(hours=oab.intervalo_horas)
        if proxima <= now:
            due.append(oab)
    return due


def run_capture_for_oab(
    session: Session,
    oab: models.OabMonitorada,
    *,
    djen: DjenClient,
    datajud: DatajudClient,
    calendar: ForensicCalendar,
    today: date | None = None,
    now: datetime | None = None,
) -> models.JobExecucao:
    """Create and run one capture job for a monitored OAB, advancing its cursor."""
    today = today or date.today()
    now = now or _utcnow()
    lookback = timedelta(days=settings.capture_lookback_days)
    base = oab.cursor_data or today
    data_inicio = base - lookback

    job = create_job(
        session,
        tipo="captura_oab",
        entidade="oab_monitorada",
        entidade_id=oab.id,
        payload={
            "oab": oab.oab,
            "uf": oab.uf,
            "escritorio_id": oab.escritorio_id,
            "data_inicio": data_inicio.isoformat(),
            "data_fim": today.isoformat(),
        },
    )
    job = run_capture_oab_job(
        session,
        job.id,
        djen=djen,
        datajud=datajud,
        calendar=calendar,
        data_inicio=data_inicio,
        data_fim=today,
    )
    oab.ultima_captura_em = now
    oab.cursor_data = today
    return job
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_capture_scheduler.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/capture/scheduler.py backend/tests/test_capture_scheduler.py
git commit -m "feat(capture): scheduler select_due + run_capture_for_oab incremental"
```

---

### Task 5: Comandos CLI `monitor-oab` e `capture-due`

**Files:**
- Modify: `backend/app/cli.py`
- Test: `backend/tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Acrescentar ao final de `backend/tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cli.py -v -k "monitor_oab or capture_due"`
Expected: FAIL (argparse `invalid choice: 'monitor-oab'`).

- [ ] **Step 3: Implement the commands**

Em `backend/app/cli.py`:

Adicionar imports após os existentes:

```python
from sqlalchemy import select

from app.capture.scheduler import run_capture_for_oab, select_due
from app.queue.jobs import create_job, mark_failed
from app.sor import models
```

Em `_build_parser`, antes do `return parser`:

```python
    monitor = sub.add_parser("monitor-oab", help="Register an OAB for scheduled capture")
    monitor.add_argument("--oab", required=True)
    monitor.add_argument("--uf", required=True)
    monitor.add_argument("--escritorio", required=True, type=int)
    monitor.add_argument("--intervalo-horas", type=int, default=12)

    sub.add_parser("capture-due", help="Run capture for all due monitored OABs")
```

Em `main`, antes de `return 0`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cli.py -v`
Expected: PASS (todos, incluindo os 2 novos).

- [ ] **Step 5: Commit**

```bash
git add backend/app/cli.py backend/tests/test_cli.py
git commit -m "feat(capture): comandos CLI monitor-oab e capture-due"
```

---

### Task 6: Endpoints `GET/POST /capturas/oab`

**Files:**
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/api/main.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Acrescentar ao final de `backend/tests/test_api.py`:

```python
def test_registrar_e_listar_oab_monitorada(client, db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()

    resp = client.post(
        "/capturas/oab",
        json={"escritorio_id": esc.id, "oab": "12345", "uf": "SP", "intervalo_horas": 6},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["oab"] == "12345"
    assert body["ativo"] is True
    assert body["intervalo_horas"] == 6

    listed = client.get("/capturas/oab")
    assert listed.status_code == 200
    assert any(o["oab"] == "12345" for o in listed.json())


def test_registrar_oab_idempotente_reativa(client, db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()

    first = client.post("/capturas/oab", json={"escritorio_id": esc.id, "oab": "999", "uf": "RJ"})
    second = client.post("/capturas/oab", json={"escritorio_id": esc.id, "oab": "999", "uf": "RJ"})
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert db_session.query(models.OabMonitorada).count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_api.py -v -k oab_monitorada`
Expected: FAIL (404 — rota inexistente).

- [ ] **Step 3: Add the schemas**

Em `backend/app/api/schemas.py`, garantir `from datetime import date, datetime` no topo (o módulo já importa de `datetime`; adicionar nomes que faltarem) e acrescentar:

```python
class OabMonitoradaOut(BaseModel):
    id: int
    escritorio_id: int
    oab: str
    uf: str
    ativo: bool
    intervalo_horas: int
    ultima_captura_em: datetime | None = None
    cursor_data: date | None = None

    model_config = {"from_attributes": True}


class OabMonitoradaCreate(BaseModel):
    escritorio_id: int | None = None
    oab: str
    uf: str
    intervalo_horas: int = 12
```

- [ ] **Step 4: Add the endpoints**

Em `backend/app/api/main.py`, incluir `OabMonitoradaOut, OabMonitoradaCreate` no import de schemas e adicionar as rotas logo após `consultar_job` (bloco de jobs):

```python
    @app.get("/capturas/oab", response_model=list[OabMonitoradaOut])
    def listar_oabs_monitoradas(
        session: Session = Depends(get_session),
    ) -> list[models.OabMonitorada]:
        stmt = select(models.OabMonitorada).order_by(models.OabMonitorada.id.desc())
        return list(session.scalars(stmt))

    @app.post("/capturas/oab", response_model=OabMonitoradaOut, status_code=201)
    def registrar_oab_monitorada(
        payload: OabMonitoradaCreate,
        session: Session = Depends(get_session),
    ) -> models.OabMonitorada:
        escritorio = _resolve_escritorio(session, payload.escritorio_id)
        existing = session.scalar(
            select(models.OabMonitorada).where(
                models.OabMonitorada.escritorio_id == escritorio.id,
                models.OabMonitorada.oab == payload.oab,
                models.OabMonitorada.uf == payload.uf,
            )
        )
        if existing is not None:
            existing.ativo = True
            existing.intervalo_horas = payload.intervalo_horas
            session.commit()
            session.refresh(existing)
            return existing
        oab = models.OabMonitorada(
            escritorio_id=escritorio.id,
            oab=payload.oab,
            uf=payload.uf,
            intervalo_horas=payload.intervalo_horas,
            ativo=True,
        )
        session.add(oab)
        session.commit()
        session.refresh(oab)
        return oab
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_api.py -v -k oab_monitorada`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/schemas.py backend/app/api/main.py backend/tests/test_api.py
git commit -m "feat(api): endpoints GET/POST /capturas/oab"
```

---

### Task 7: Suíte completa + lint

**Files:** nenhum (verificação).

- [ ] **Step 1: Run full suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: tudo verde (113 anteriores + os novos), 0 falhas.

- [ ] **Step 2: Lint**

Run: `./.venv/Scripts/python.exe -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 3: Smoke real (manual, fora do CI)**

Pré-requisito: `CAUSOR_DATAJUD_API_KEY` no `.env` e Postgres migrado (`alembic upgrade head`).

```
python -m app.cli monitor-oab --oab <OAB_REAL> --uf <UF> --escritorio 1
python -m app.cli capture-due
```
Expected: o segundo comando imprime `1 OAB(s) para capturar` e um job `completed` com contagem de intimações reais. Confirmar via `GET /intimacoes` e `GET /prazos` que entraram dados reais.

---

## Validação da fase

- [ ] `pytest` verde com os novos testes (modelo, executor, scheduler, CLI, API).
- [ ] `ruff check .` limpo.
- [ ] Migration `d3b1c0f5a9e2` aplica no Postgres local.
- [ ] `capture-due` roda uma OAB real e popula o SOR (smoke manual).
- [ ] Nenhum segredo em payload/resultado de job (captura não usa credencial de assinatura).
- [ ] Contrato `job_execucao` intacto para um worker Redis/RQ entrar depois.

## Fora de escopo (próximos planos)

- Worker Redis/RQ real (o contrato já está pronto; troca o executor in-process).
- Tela "Capturas" no frontend (cobertura/falhas) — depois do primeiro protocolo, conforme blueprint.
- Conector PJe e assinatura em nuvem — dependem do escritório-piloto e do provedor escolhido.
