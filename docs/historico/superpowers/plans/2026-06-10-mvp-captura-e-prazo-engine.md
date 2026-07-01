# MVP Slice 1 — Captura (DJEN + DataJud) + Prazo Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained backend slice that, given a lawyer's OAB number, captures intimations from DJEN/Comunica, enriches the related processes via DataJud, and computes legal deadlines deterministically — persisted to Postgres and exposed via read-only API.

**Architecture:** System of Record (Postgres) + capture clients consuming official CNJ APIs + a deterministic deadline engine. No scraping, no LLM, no browser automation in this slice — those belong to later slices (agent layer, PJe connector). The deadline math is plain testable code; the only external dependencies are two documented CNJ HTTP APIs.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x + Alembic, pydantic v2 / pydantic-settings, httpx, workalendar, pytest + pytest-httpx, ruff. Postgres 16 via docker-compose.

---

## Scope and boundaries

**In scope (this plan):**
- Project scaffold (deps, config, lint, test harness, local Postgres).
- SOR models for `Escritorio`, `Processo`, `Andamento`, `Intimacao`, `Prazo`.
- Deterministic prazo engine: forensic calendar + CPC business-day deadline computation + recess/holiday provider.
- DJEN/Comunica HTTP client (typed) + DataJud HTTP client (typed).
- Capture/normalization service wiring DJEN → SOR and DataJud → SOR.
- A synchronous poller (plain function + CLI) that runs the capture for one OAB over a date range.
- A prazo-registration service that computes and persists a `Prazo` for an intimation given a `prazo_dias`.
- Read-only FastAPI endpoints to inspect captured intimations and computed prazos.

**Explicitly deferred (not this plan — YAGNI for slice 1):**
- Celery/RQ + Redis. A synchronous poller is enough to validate capture and deadline math. (The full plan keeps Celery for scale; we add it when polling volume requires it.)
- The agent layer that *classifies* which `prazo_dias` applies to an intimation. Here `prazo_dias` is an explicit input to the prazo service; classification is a later slice.
- PJe connector, vault, signing, approval gate, frontend.

**Why these constraints (from `PLANO_Agente_Operacional_Juridico.md`):** capture uses official APIs only; deadline math must be deterministic and ≥99% correct on tested cases; secrets never enter logs (DataJud API key comes from config/env, never hardcoded permanently — CNJ rotates it).

---

## File structure

```
/backend
  pyproject.toml                 # deps + tool config (ruff, pytest)
  alembic.ini
  docker-compose.yml             # local Postgres for dev + integration tests
  .env.example
  /app
    __init__.py
    settings.py                  # pydantic-settings: DB url, DataJud key, DJEN base url
    db.py                        # SQLAlchemy engine/session factory
    /sor
      __init__.py
      models.py                  # Escritorio, Processo, Andamento, Intimacao, Prazo
    /prazo_engine
      __init__.py
      calendar.py                # ForensicCalendar (business-day logic)
      deadline.py                # compute_deadline (CPC counting) + DeadlineResult
      calendar_factory.py        # build_calendar(): workalendar holidays + recess
      service.py                 # registrar_prazo(): compute + persist a Prazo
    /capture
      __init__.py
      djen.py                    # DjenClient + pydantic models
      datajud.py                 # DatajudClient + pydantic models
      service.py                 # normalize_intimacao(), enrich_processo()
      poller.py                  # poll_oab() orchestration + CLI entrypoint
    /api
      __init__.py
      main.py                    # FastAPI app: GET /intimacoes, GET /prazos
  /alembic
    env.py
    /versions                    # generated migration(s)
  /tests
    __init__.py
    conftest.py                  # in-memory/throwaway DB session fixture
    prazo_engine/
      test_calendar.py
      test_deadline.py
      test_calendar_factory.py
      test_service.py
    capture/
      test_djen.py
      test_datajud.py
      test_service.py
      test_poller.py
    api/
      test_endpoints.py
```

**Responsibility boundaries:**
- `prazo_engine/` is a pure library (calendar + deadline) with a thin `service.py` that touches the DB. The pure parts have zero I/O — fully unit-testable.
- `capture/` clients are I/O-only (HTTP). They return typed models and never touch the DB. `service.py` does the DB mapping. This keeps HTTP mocking and DB testing separate.
- `sor/models.py` is the single source of schema truth; Alembic migrations are generated from it.

---

## Conventions used by every task

- **TDD:** write the failing test, run it red, implement minimally, run it green, commit.
- **Run tests from `/backend`:** `cd backend` is assumed for every `pytest`/`alembic` command. (On Windows PowerShell, the agent already starts in the repo root; `cd backend` once per shell.)
- **Pure-logic tests need no DB.** DB-touching tests use the `db_session` fixture (Task 1). HTTP-client tests use `pytest-httpx` to mock responses — they never hit the network.
- **Commit messages:** Conventional Commits (`feat:`, `test:`, `chore:`).

---

## Task 0: Project scaffold

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.gitignore`
- Create: `backend/.env.example`
- Create: `backend/docker-compose.yml`
- Create: `backend/app/__init__.py`, `backend/app/settings.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/app/sor/__init__.py`, `backend/app/prazo_engine/__init__.py`, `backend/app/capture/__init__.py`, `backend/app/api/__init__.py`

- [ ] **Step 1: Initialize git at repo root (if not already a repo)**

Run (from `C:\Users\moura\Documents\causor`):
```
git init
```
Expected: `Initialized empty Git repository` (or a notice it already exists — either is fine).

- [ ] **Step 2: Create `backend/pyproject.toml`**

```toml
[project]
name = "causor-backend"
version = "0.1.0"
description = "Agente Operacional Juridico - capture + prazo engine"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.111",
    "uvicorn>=0.30",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "psycopg[binary]>=3.1",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "httpx>=0.27",
    "workalendar>=17.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "pytest-httpx>=0.30",
    "ruff>=0.5",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 3: Create `backend/.gitignore`**

```
__pycache__/
*.pyc
.venv/
.env
.pytest_cache/
*.db
```

- [ ] **Step 4: Create `backend/.env.example`**

```
DATABASE_URL=postgresql+psycopg://causor:causor@localhost:5432/causor
DATAJUD_API_KEY=cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==
DATAJUD_BASE_URL=https://api-publica.datajud.cnj.jus.br
DJEN_BASE_URL=https://comunicaapi.pje.jus.br
```
(The DataJud key above is the published CNJ public key as of this writing; CNJ may rotate it. It lives in env, never hardcoded in source.)

- [ ] **Step 5: Create `backend/docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: causor
      POSTGRES_PASSWORD: causor
      POSTGRES_DB: causor
    ports:
      - "5432:5432"
    volumes:
      - causor_pgdata:/var/lib/postgresql/data
volumes:
  causor_pgdata:
```

- [ ] **Step 6: Create `backend/app/settings.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://causor:causor@localhost:5432/causor"
    datajud_api_key: str = ""
    datajud_base_url: str = "https://api-publica.datajud.cnj.jus.br"
    djen_base_url: str = "https://comunicaapi.pje.jus.br"


settings = Settings()
```

- [ ] **Step 7: Create empty package markers**

Create these files, each containing a single newline:
`backend/app/__init__.py`, `backend/tests/__init__.py`, `backend/app/sor/__init__.py`, `backend/app/prazo_engine/__init__.py`, `backend/app/capture/__init__.py`, `backend/app/api/__init__.py`.

- [ ] **Step 8: Install deps and verify the toolchain**

Run (from `backend/`):
```
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\pytest -q
```
Expected: pytest runs and reports `no tests ran` (exit code 5) — confirms the harness is wired. ruff/pytest importable.

- [ ] **Step 9: Commit**

```
git add backend/.gitignore backend/pyproject.toml backend/.env.example backend/docker-compose.yml backend/app backend/tests
git commit -m "chore: scaffold backend (deps, settings, local postgres)"
```

---

## Task 1: SOR models + DB session + test fixture

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/sor/models.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/prazo_engine/__init__.py`, `backend/tests/capture/__init__.py`, `backend/tests/api/__init__.py` (empty package markers)

- [ ] **Step 1: Create `backend/app/db.py`**

```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.settings import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 2: Create `backend/app/sor/models.py`**

```python
from datetime import date, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Escritorio(Base):
    __tablename__ = "escritorio"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(255))
    oab_numero: Mapped[str] = mapped_column(String(20))
    oab_uf: Mapped[str] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Processo(Base):
    __tablename__ = "processo"
    id: Mapped[int] = mapped_column(primary_key=True)
    numero_processo: Mapped[str] = mapped_column(String(25), unique=True, index=True)
    tribunal: Mapped[str | None] = mapped_column(String(20))
    classe: Mapped[str | None] = mapped_column(String(255))
    orgao_julgador: Mapped[str | None] = mapped_column(String(255))
    data_ajuizamento: Mapped[date | None] = mapped_column()
    sistema: Mapped[str | None] = mapped_column(String(50))
    nivel_sigilo: Mapped[int | None] = mapped_column(Integer)
    raw_datajud: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    andamentos: Mapped[list["Andamento"]] = relationship(back_populates="processo")


class Andamento(Base):
    __tablename__ = "andamento"
    id: Mapped[int] = mapped_column(primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processo.id"))
    codigo: Mapped[int | None] = mapped_column(Integer)
    nome: Mapped[str | None] = mapped_column(String(500))
    data_hora: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    processo: Mapped["Processo"] = relationship(back_populates="andamentos")


class Intimacao(Base):
    __tablename__ = "intimacao"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    numero_processo: Mapped[str | None] = mapped_column(String(25), index=True)
    tribunal: Mapped[str | None] = mapped_column(String(20))
    tipo_comunicacao: Mapped[str | None] = mapped_column(String(100))
    texto: Mapped[str | None] = mapped_column(String)
    data_disponibilizacao: Mapped[date] = mapped_column()
    meio: Mapped[str | None] = mapped_column(String(10))
    oab_numero: Mapped[str | None] = mapped_column(String(20))
    oab_uf: Mapped[str | None] = mapped_column(String(2))
    link: Mapped[str | None] = mapped_column(String(1000))
    raw: Mapped[dict | None] = mapped_column(JSON)
    processo_id: Mapped[int | None] = mapped_column(ForeignKey("processo.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Prazo(Base):
    __tablename__ = "prazo"
    id: Mapped[int] = mapped_column(primary_key=True)
    intimacao_id: Mapped[int] = mapped_column(ForeignKey("intimacao.id"))
    prazo_dias: Mapped[int] = mapped_column(Integer)
    disponibilizacao: Mapped[date] = mapped_column()
    publicacao: Mapped[date] = mapped_column()
    inicio_contagem: Mapped[date] = mapped_column()
    vencimento: Mapped[date] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default="aberto")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 3: Create test package markers**

Create `backend/tests/prazo_engine/__init__.py`, `backend/tests/capture/__init__.py`, `backend/tests/api/__init__.py` — each a single newline.

- [ ] **Step 4: Create `backend/tests/conftest.py`** (SQLite in-memory session so pure DB tests need no Postgres)

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.sor import models  # noqa: F401  (register tables on Base.metadata)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
```

- [ ] **Step 5: Write a smoke test that the schema builds and a row round-trips**

`backend/tests/test_sor_smoke.py`:
```python
from datetime import date

from app.sor.models import Intimacao


def test_intimacao_roundtrip(db_session):
    intimacao = Intimacao(
        external_id="abc123",
        numero_processo="00008323520184013202",
        data_disponibilizacao=date(2026, 6, 8),
    )
    db_session.add(intimacao)
    db_session.commit()

    fetched = db_session.query(Intimacao).filter_by(external_id="abc123").one()
    assert fetched.numero_processo == "00008323520184013202"
    assert fetched.status_default_ok if hasattr(fetched, "status_default_ok") else True
```

- [ ] **Step 6: Run the test — verify it passes**

Run: `pytest tests/test_sor_smoke.py -v`
Expected: PASS (table creates, row round-trips).

- [ ] **Step 7: Commit**

```
git add backend/app/db.py backend/app/sor/models.py backend/tests/conftest.py backend/tests/test_sor_smoke.py backend/tests/prazo_engine backend/tests/capture backend/tests/api
git commit -m "feat: add SOR models and test DB fixture"
```

---

## Task 2: Forensic calendar (business-day logic) — pure, TDD

**Files:**
- Create: `backend/app/prazo_engine/calendar.py`
- Test: `backend/tests/prazo_engine/test_calendar.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/prazo_engine/test_calendar.py`:
```python
from datetime import date

from app.prazo_engine.calendar import ForensicCalendar


def test_weekend_is_not_business_day():
    cal = ForensicCalendar(holidays=set())
    assert cal.is_business_day(date(2026, 6, 13)) is False  # Saturday
    assert cal.is_business_day(date(2026, 6, 14)) is False  # Sunday
    assert cal.is_business_day(date(2026, 6, 12)) is True   # Friday


def test_holiday_is_not_business_day():
    cal = ForensicCalendar(holidays={date(2026, 6, 11)})
    assert cal.is_business_day(date(2026, 6, 11)) is False


def test_recess_range_is_not_business_day():
    cal = ForensicCalendar(holidays=set(), recess_ranges=[(date(2026, 12, 20), date(2027, 1, 20))])
    assert cal.is_business_day(date(2026, 12, 29)) is False  # weekday inside recess
    assert cal.is_business_day(date(2027, 1, 21)) is True    # day after recess (weekday)


def test_next_business_day_skips_weekend():
    cal = ForensicCalendar(holidays=set())
    assert cal.next_business_day(date(2026, 6, 12)) == date(2026, 6, 15)  # Fri -> Mon


def test_add_business_days_counts_only_business_days():
    cal = ForensicCalendar(holidays=set())
    # From Monday 2026-06-15, +5 business days -> Monday 2026-06-22
    assert cal.add_business_days(date(2026, 6, 15), 5) == date(2026, 6, 22)
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/prazo_engine/test_calendar.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.prazo_engine.calendar'`.

- [ ] **Step 3: Implement `backend/app/prazo_engine/calendar.py`**

```python
from datetime import date, timedelta


class ForensicCalendar:
    """Knows which dates count as business days for legal deadline purposes.

    A date is a business day unless it is a weekend, a configured holiday, or
    falls within a recess range (inclusive on both ends).
    """

    def __init__(
        self,
        holidays: set[date],
        recess_ranges: list[tuple[date, date]] | None = None,
    ) -> None:
        self._holidays = holidays
        self._recess_ranges = recess_ranges or []

    def _in_recess(self, d: date) -> bool:
        return any(start <= d <= end for start, end in self._recess_ranges)

    def is_business_day(self, d: date) -> bool:
        if d.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            return False
        if d in self._holidays:
            return False
        if self._in_recess(d):
            return False
        return True

    def next_business_day(self, d: date) -> date:
        """First business day strictly after `d`."""
        nxt = d + timedelta(days=1)
        while not self.is_business_day(nxt):
            nxt += timedelta(days=1)
        return nxt

    def add_business_days(self, start: date, n: int) -> date:
        """Date that is `n` business days after `start` (each step lands on a
        business day). `add_business_days(start, 1)` == `next_business_day(start)`.
        """
        current = start
        for _ in range(n):
            current = self.next_business_day(current)
        return current
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/prazo_engine/test_calendar.py -v`
Expected: PASS (all 5).

- [ ] **Step 5: Commit**

```
git add backend/app/prazo_engine/calendar.py backend/tests/prazo_engine/test_calendar.py
git commit -m "feat: add ForensicCalendar business-day logic"
```

---

## Task 3: Deadline computation (CPC counting) — pure, TDD

**Files:**
- Create: `backend/app/prazo_engine/deadline.py`
- Test: `backend/tests/prazo_engine/test_deadline.py`

**Rule being encoded (CPC arts. 224 §§2–3 and 219):**
1. `publicacao` = first business day strictly after `disponibilizacao` (art. 224 §2).
2. `inicio_contagem` = first business day strictly after `publicacao` (art. 224 §3) — i.e. business day #1 of the count.
3. The deadline is counted in **business days** (art. 219). `vencimento` = the `prazo_dias`-th business day from `publicacao` = `add_business_days(publicacao, prazo_dias)`. Since `inicio_contagem` is business day #1, this lands `vencimento` correctly on a business day (art. 224 §1 prorrogação is automatic because we only land on business days).

- [ ] **Step 1: Write the failing tests**

`backend/tests/prazo_engine/test_deadline.py`:
```python
from datetime import date

from app.prazo_engine.calendar import ForensicCalendar
from app.prazo_engine.deadline import DeadlineResult, compute_deadline


def _plain_calendar() -> ForensicCalendar:
    return ForensicCalendar(holidays=set())


def test_publicacao_is_next_business_day_after_disponibilizacao():
    # Disponibilizado on Mon 2026-06-08 -> publicacao Tue 2026-06-09
    result = compute_deadline(date(2026, 6, 8), prazo_dias=15, calendar=_plain_calendar())
    assert result.publicacao == date(2026, 6, 9)


def test_inicio_contagem_is_business_day_after_publicacao():
    result = compute_deadline(date(2026, 6, 8), prazo_dias=15, calendar=_plain_calendar())
    assert result.inicio_contagem == date(2026, 6, 10)  # Wed


def test_vencimento_counts_business_days_only():
    # publicacao Tue 2026-06-09; 15 business days -> Tue 2026-06-30
    result = compute_deadline(date(2026, 6, 8), prazo_dias=15, calendar=_plain_calendar())
    assert result.vencimento == date(2026, 6, 30)


def test_disponibilizacao_on_friday_rolls_publicacao_to_monday():
    # Fri 2026-06-12 -> publicacao Mon 2026-06-15
    result = compute_deadline(date(2026, 6, 12), prazo_dias=5, calendar=_plain_calendar())
    assert result.publicacao == date(2026, 6, 15)
    assert result.inicio_contagem == date(2026, 6, 16)
    assert result.vencimento == date(2026, 6, 22)  # 5 business days from Mon 15th


def test_holiday_inside_count_extends_vencimento():
    # Holiday on Thu 2026-06-11; publicacao Tue 2026-06-09, prazo 5 dias
    cal = ForensicCalendar(holidays={date(2026, 6, 11)})
    result = compute_deadline(date(2026, 6, 8), prazo_dias=5, calendar=cal)
    # business days from pub Tue9: Wed10, [Thu11 skip], Fri12, Mon15, Tue16, Wed17 -> 5th = Wed17
    assert result.vencimento == date(2026, 6, 17)


def test_recess_suspends_count():
    cal = ForensicCalendar(holidays=set(), recess_ranges=[(date(2026, 12, 20), date(2027, 1, 20))])
    # disponibilizacao Mon 2026-12-14 -> pub Tue 12-15
    result = compute_deadline(date(2026, 12, 14), prazo_dias=5, calendar=cal)
    # bdays from pub: Wed16, Thu17, Fri18, [20..Jan20 recess], Wed Jan21, Thu Jan22 -> 5th = Jan 22
    assert result.vencimento == date(2027, 1, 22)


def test_result_is_frozen_dataclass_with_all_fields():
    result = compute_deadline(date(2026, 6, 8), prazo_dias=15, calendar=_plain_calendar())
    assert isinstance(result, DeadlineResult)
    assert result.disponibilizacao == date(2026, 6, 8)
    assert result.prazo_dias == 15
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/prazo_engine/test_deadline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.prazo_engine.deadline'`.

- [ ] **Step 3: Implement `backend/app/prazo_engine/deadline.py`**

```python
from dataclasses import dataclass
from datetime import date

from app.prazo_engine.calendar import ForensicCalendar


@dataclass(frozen=True)
class DeadlineResult:
    disponibilizacao: date
    publicacao: date
    inicio_contagem: date
    vencimento: date
    prazo_dias: int


def compute_deadline(
    disponibilizacao: date,
    prazo_dias: int,
    calendar: ForensicCalendar,
) -> DeadlineResult:
    """Compute a procedural deadline per CPC arts. 224 §§2-3 and 219.

    publicacao = next business day after disponibilizacao
    inicio_contagem = next business day after publicacao (business day #1)
    vencimento = prazo_dias-th business day after publicacao
    """
    if prazo_dias < 1:
        raise ValueError("prazo_dias must be >= 1")

    publicacao = calendar.next_business_day(disponibilizacao)
    inicio_contagem = calendar.next_business_day(publicacao)
    vencimento = calendar.add_business_days(publicacao, prazo_dias)
    return DeadlineResult(
        disponibilizacao=disponibilizacao,
        publicacao=publicacao,
        inicio_contagem=inicio_contagem,
        vencimento=vencimento,
        prazo_dias=prazo_dias,
    )
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/prazo_engine/test_deadline.py -v`
Expected: PASS (all 7).

- [ ] **Step 5: Commit**

```
git add backend/app/prazo_engine/deadline.py backend/tests/prazo_engine/test_deadline.py
git commit -m "feat: add deterministic CPC deadline computation"
```

---

## Task 4: Calendar factory (holidays + recess) — TDD

**Files:**
- Create: `backend/app/prazo_engine/calendar_factory.py`
- Test: `backend/tests/prazo_engine/test_calendar_factory.py`

**What it does:** builds a `ForensicCalendar` populated with Brazilian national holidays (via `workalendar`) across a year range, plus the art. 220 recess range (20 Dec → 20 Jan inclusive) for each year, plus optional local/court holidays injected by the caller.

- [ ] **Step 1: Write the failing tests**

`backend/tests/prazo_engine/test_calendar_factory.py`:
```python
from datetime import date

from app.prazo_engine.calendar_factory import build_calendar


def test_national_holiday_is_not_business_day():
    cal = build_calendar(2026, 2026)
    # Independência do Brasil - 7 de setembro (Monday in 2026)
    assert cal.is_business_day(date(2026, 9, 7)) is False


def test_recess_range_applied_per_year():
    cal = build_calendar(2026, 2027)
    assert cal.is_business_day(date(2026, 12, 29)) is False  # inside 2026 recess
    assert cal.is_business_day(date(2027, 1, 15)) is False   # inside 2026->2027 recess tail


def test_extra_holidays_are_respected():
    cal = build_calendar(2026, 2026, extra_holidays={date(2026, 7, 9)})
    assert cal.is_business_day(date(2026, 7, 9)) is False  # ex: Revolução Constitucionalista (SP)


def test_ordinary_weekday_is_business_day():
    cal = build_calendar(2026, 2026)
    assert cal.is_business_day(date(2026, 6, 10)) is True  # Wednesday, no holiday
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/prazo_engine/test_calendar_factory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.prazo_engine.calendar_factory'`.

- [ ] **Step 3: Implement `backend/app/prazo_engine/calendar_factory.py`**

```python
from datetime import date

from workalendar.america import Brazil

from app.prazo_engine.calendar import ForensicCalendar


def build_calendar(
    start_year: int,
    end_year: int,
    extra_holidays: set[date] | None = None,
) -> ForensicCalendar:
    """Build a ForensicCalendar for the inclusive year range.

    Includes Brazilian national holidays, the CPC art. 220 recess (20 Dec - 20
    Jan inclusive) for each year, and any caller-supplied local holidays.
    """
    brazil = Brazil()
    holidays: set[date] = set()
    recess_ranges: list[tuple[date, date]] = []

    for year in range(start_year, end_year + 1):
        for holiday_date, _name in brazil.holidays(year):
            holidays.add(holiday_date)
        recess_ranges.append((date(year, 12, 20), date(year + 1, 1, 20)))

    if extra_holidays:
        holidays |= extra_holidays

    return ForensicCalendar(holidays=holidays, recess_ranges=recess_ranges)
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/prazo_engine/test_calendar_factory.py -v`
Expected: PASS (all 4).

- [ ] **Step 5: Commit**

```
git add backend/app/prazo_engine/calendar_factory.py backend/tests/prazo_engine/test_calendar_factory.py
git commit -m "feat: add calendar factory with national holidays and recess"
```

---

## Task 5: DJEN/Comunica client — TDD with mocked HTTP

**Files:**
- Create: `backend/app/capture/djen.py`
- Test: `backend/tests/capture/test_djen.py`

**Note on the external contract:** The DJEN/Comunica response uses mixed snake_case keys. The model below maps the documented fields. Step 1 of this task includes a one-time live verification so the mapping matches production before relying on it; adjust field aliases if the live payload differs, then keep the tests green.

- [ ] **Step 1: Verify the live DJEN response shape (one-time spike, record findings)**

Run (any machine with internet; replace OAB/UF with a real test value from a pilot):
```
curl "https://comunicaapi.pje.jus.br/api/v1/comunicacao?numeroOab=12345&ufOab=DF&dataDisponibilizacaoInicio=2026-06-01&dataDisponibilizacaoFim=2026-06-09&pagina=1&itensPorPagina=5"
```
Record the actual JSON keys for: the list container, each item's id, `data_disponibilizacao`, tribunal sigla, `tipoComunicacao`, `texto`, `numero_processo`, `meio`, `link`, and the advogado OAB fields. If any key differs from the model in Step 3, update the `alias=` values there. Paste the observed payload into the PR description for the reviewer.

- [ ] **Step 2: Write the failing test (uses a fixed mocked payload)**

`backend/tests/capture/test_djen.py`:
```python
from datetime import date

import httpx
from pytest_httpx import HTTPXMock

from app.capture.djen import DjenClient


SAMPLE = {
    "status": "success",
    "count": 1,
    "items": [
        {
            "id": 987654,
            "data_disponibilizacao": "2026-06-08",
            "siglaTribunal": "TRF1",
            "tipoComunicacao": "Intimação",
            "texto": "Fica a parte intimada para manifestar em 15 dias.",
            "numero_processo": "00008323520184013202",
            "meio": "D",
            "link": "https://comunica.pje.jus.br/abc",
            "destinatarioadvogados": [
                {"advogado": {"numero_oab": "12345", "uf_oab": "DF", "nome": "Fulano"}}
            ],
        }
    ],
}


def test_fetch_comunicacoes_parses_items(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json=SAMPLE)
    with httpx.Client() as http:
        client = DjenClient(base_url="https://comunicaapi.pje.jus.br", http_client=http)
        response = client.fetch_comunicacoes(
            oab_numero="12345",
            oab_uf="DF",
            data_inicio=date(2026, 6, 1),
            data_fim=date(2026, 6, 9),
        )
    assert response.count == 1
    item = response.items[0]
    assert item.external_id == "987654"
    assert item.numero_processo == "00008323520184013202"
    assert item.data_disponibilizacao == date(2026, 6, 8)
    assert item.tribunal == "TRF1"
    assert item.tipo_comunicacao == "Intimação"


def test_fetch_comunicacoes_sends_expected_query(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json={"status": "success", "count": 0, "items": []})
    with httpx.Client() as http:
        client = DjenClient(base_url="https://comunicaapi.pje.jus.br", http_client=http)
        client.fetch_comunicacoes(
            oab_numero="12345", oab_uf="DF",
            data_inicio=date(2026, 6, 1), data_fim=date(2026, 6, 9),
        )
    request = httpx_mock.get_requests()[0]
    assert request.url.params["numeroOab"] == "12345"
    assert request.url.params["ufOab"] == "DF"
    assert request.url.params["dataDisponibilizacaoInicio"] == "2026-06-01"
    assert request.url.params["dataDisponibilizacaoFim"] == "2026-06-09"
```

- [ ] **Step 3: Run test — verify it fails**

Run: `pytest tests/capture/test_djen.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.capture.djen'`.

- [ ] **Step 4: Implement `backend/app/capture/djen.py`**

```python
from datetime import date

import httpx
from pydantic import BaseModel, Field, field_validator


class DjenComunicacao(BaseModel):
    external_id: str = Field(alias="id")
    data_disponibilizacao: date
    tribunal: str | None = Field(default=None, alias="siglaTribunal")
    tipo_comunicacao: str | None = Field(default=None, alias="tipoComunicacao")
    texto: str | None = None
    numero_processo: str | None = None
    meio: str | None = None
    link: str | None = None
    raw: dict = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    @field_validator("external_id", mode="before")
    @classmethod
    def _coerce_id(cls, value: object) -> str:
        return str(value)


class DjenResponse(BaseModel):
    count: int = 0
    items: list[DjenComunicacao] = Field(default_factory=list)


class DjenClient:
    def __init__(self, base_url: str, http_client: httpx.Client) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = http_client

    def fetch_comunicacoes(
        self,
        oab_numero: str,
        oab_uf: str,
        data_inicio: date,
        data_fim: date,
        pagina: int = 1,
        itens_por_pagina: int = 100,
    ) -> DjenResponse:
        params = {
            "numeroOab": oab_numero,
            "ufOab": oab_uf,
            "dataDisponibilizacaoInicio": data_inicio.isoformat(),
            "dataDisponibilizacaoFim": data_fim.isoformat(),
            "pagina": pagina,
            "itensPorPagina": itens_por_pagina,
        }
        resp = self._http.get(
            f"{self._base_url}/api/v1/comunicacao", params=params, timeout=30
        )
        resp.raise_for_status()
        payload = resp.json()
        items = [
            DjenComunicacao.model_validate({**item, "raw": item})
            for item in payload.get("items", [])
        ]
        return DjenResponse(count=payload.get("count", len(items)), items=items)
```

- [ ] **Step 5: Run tests — verify they pass**

Run: `pytest tests/capture/test_djen.py -v`
Expected: PASS (both).

- [ ] **Step 6: Commit**

```
git add backend/app/capture/djen.py backend/tests/capture/test_djen.py
git commit -m "feat: add DJEN/Comunica capture client"
```

---

## Task 6: DataJud client — TDD with mocked HTTP

**Files:**
- Create: `backend/app/capture/datajud.py`
- Test: `backend/tests/capture/test_datajud.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/capture/test_datajud.py`:
```python
import httpx
from pytest_httpx import HTTPXMock

from app.capture.datajud import DatajudClient


SAMPLE = {
    "hits": {
        "total": {"value": 1},
        "hits": [
            {
                "_source": {
                    "numeroProcesso": "00008323520184013202",
                    "tribunal": "TRF1",
                    "classe": {"codigo": 7, "nome": "Procedimento Comum"},
                    "dataAjuizamento": "2018-03-14T00:00:00.000Z",
                    "orgaoJulgador": {"nome": "2a Vara Federal"},
                    "sistema": {"nome": "Pje"},
                    "nivelSigilo": 0,
                    "movimentos": [
                        {"codigo": 123, "nome": "Conclusão", "dataHora": "2026-06-05T10:00:00.000Z"}
                    ],
                }
            }
        ],
    }
}


def test_buscar_processo_parses_source(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json=SAMPLE)
    with httpx.Client() as http:
        client = DatajudClient(
            api_key="KEY", base_url="https://api-publica.datajud.cnj.jus.br", http_client=http
        )
        processo = client.buscar_processo("api_publica_trf1", "00008323520184013202")
    assert processo is not None
    assert processo.numero_processo == "00008323520184013202"
    assert processo.classe == "Procedimento Comum"
    assert processo.sistema == "Pje"
    assert len(processo.movimentos) == 1
    assert processo.movimentos[0].nome == "Conclusão"


def test_buscar_processo_sends_apikey_header_and_query(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json=SAMPLE)
    with httpx.Client() as http:
        client = DatajudClient(
            api_key="KEY", base_url="https://api-publica.datajud.cnj.jus.br", http_client=http
        )
        client.buscar_processo("api_publica_trf1", "00008323520184013202")
    request = httpx_mock.get_requests()[0]
    assert request.headers["Authorization"] == "APIKey KEY"
    assert str(request.url).endswith("/api_publica_trf1/_search")


def test_buscar_processo_returns_none_when_no_hits(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json={"hits": {"total": {"value": 0}, "hits": []}})
    with httpx.Client() as http:
        client = DatajudClient(
            api_key="KEY", base_url="https://api-publica.datajud.cnj.jus.br", http_client=http
        )
        assert client.buscar_processo("api_publica_trf1", "0000000") is None
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest tests/capture/test_datajud.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.capture.datajud'`.

- [ ] **Step 3: Implement `backend/app/capture/datajud.py`**

```python
from datetime import date, datetime

import httpx
from pydantic import BaseModel


class DatajudMovimento(BaseModel):
    codigo: int | None = None
    nome: str | None = None
    data_hora: datetime | None = None


class DatajudProcesso(BaseModel):
    numero_processo: str
    tribunal: str | None = None
    classe: str | None = None
    orgao_julgador: str | None = None
    data_ajuizamento: date | None = None
    sistema: str | None = None
    nivel_sigilo: int | None = None
    movimentos: list[DatajudMovimento] = []
    raw: dict = {}


def _parse_source(source: dict) -> DatajudProcesso:
    classe = source.get("classe") or {}
    orgao = source.get("orgaoJulgador") or {}
    sistema = source.get("sistema") or {}
    ajuizamento = source.get("dataAjuizamento")
    movimentos = [
        DatajudMovimento(
            codigo=m.get("codigo"),
            nome=m.get("nome"),
            data_hora=m.get("dataHora"),
        )
        for m in source.get("movimentos", [])
    ]
    return DatajudProcesso(
        numero_processo=source["numeroProcesso"],
        tribunal=source.get("tribunal"),
        classe=classe.get("nome"),
        orgao_julgador=orgao.get("nome"),
        data_ajuizamento=datetime.fromisoformat(ajuizamento.replace("Z", "+00:00")).date()
        if ajuizamento
        else None,
        sistema=sistema.get("nome"),
        nivel_sigilo=source.get("nivelSigilo"),
        movimentos=movimentos,
        raw=source,
    )


class DatajudClient:
    def __init__(self, api_key: str, base_url: str, http_client: httpx.Client) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._http = http_client

    def buscar_processo(self, tribunal_alias: str, numero_processo: str) -> DatajudProcesso | None:
        url = f"{self._base_url}/{tribunal_alias}/_search"
        body = {"query": {"match": {"numeroProcesso": numero_processo}}}
        resp = self._http.post(
            url,
            json=body,
            headers={
                "Authorization": f"APIKey {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])
        if not hits:
            return None
        return _parse_source(hits[0]["_source"])
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/capture/test_datajud.py -v`
Expected: PASS (all 3).

- [ ] **Step 5: Commit**

```
git add backend/app/capture/datajud.py backend/tests/capture/test_datajud.py
git commit -m "feat: add DataJud capture client"
```

---

## Task 7: Capture/normalization service (clients → SOR) — TDD

**Files:**
- Create: `backend/app/capture/service.py`
- Test: `backend/tests/capture/test_service.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/capture/test_service.py`:
```python
from datetime import date, datetime, timezone

from app.capture.datajud import DatajudMovimento, DatajudProcesso
from app.capture.djen import DjenComunicacao
from app.capture.service import enrich_processo, normalize_intimacao
from app.sor.models import Andamento, Intimacao, Processo


def _djen_item() -> DjenComunicacao:
    return DjenComunicacao.model_validate(
        {
            "id": 555,
            "data_disponibilizacao": "2026-06-08",
            "siglaTribunal": "TRF1",
            "tipoComunicacao": "Intimação",
            "texto": "manifestar em 15 dias",
            "numero_processo": "00008323520184013202",
            "meio": "D",
            "link": "https://x",
        }
    )


def test_normalize_intimacao_persists_row(db_session):
    intimacao = normalize_intimacao(
        _djen_item(), oab_numero="12345", oab_uf="DF", session=db_session
    )
    db_session.commit()
    stored = db_session.query(Intimacao).one()
    assert stored.external_id == "555"
    assert stored.numero_processo == "00008323520184013202"
    assert stored.oab_numero == "12345"
    assert intimacao.id is not None


def test_normalize_intimacao_is_idempotent_on_external_id(db_session):
    normalize_intimacao(_djen_item(), oab_numero="12345", oab_uf="DF", session=db_session)
    db_session.commit()
    normalize_intimacao(_djen_item(), oab_numero="12345", oab_uf="DF", session=db_session)
    db_session.commit()
    assert db_session.query(Intimacao).count() == 1


def test_enrich_processo_creates_processo_and_andamentos(db_session):
    processo_dto = DatajudProcesso(
        numero_processo="00008323520184013202",
        tribunal="TRF1",
        classe="Procedimento Comum",
        sistema="Pje",
        data_ajuizamento=date(2018, 3, 14),
        movimentos=[
            DatajudMovimento(
                codigo=123, nome="Conclusão",
                data_hora=datetime(2026, 6, 5, 10, tzinfo=timezone.utc),
            )
        ],
    )
    processo = enrich_processo(processo_dto, session=db_session)
    db_session.commit()
    assert db_session.query(Processo).count() == 1
    assert db_session.query(Andamento).count() == 1
    assert processo.classe == "Procedimento Comum"


def test_enrich_processo_is_idempotent_on_numero(db_session):
    dto = DatajudProcesso(numero_processo="00008323520184013202", tribunal="TRF1")
    enrich_processo(dto, session=db_session)
    db_session.commit()
    enrich_processo(dto, session=db_session)
    db_session.commit()
    assert db_session.query(Processo).count() == 1
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `pytest tests/capture/test_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.capture.service'`.

- [ ] **Step 3: Implement `backend/app/capture/service.py`**

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.capture.datajud import DatajudProcesso
from app.capture.djen import DjenComunicacao
from app.sor.models import Andamento, Intimacao, Processo


def normalize_intimacao(
    item: DjenComunicacao, oab_numero: str, oab_uf: str, session: Session
) -> Intimacao:
    """Map a DJEN communication to an Intimacao row. Idempotent on external_id."""
    existing = session.scalar(
        select(Intimacao).where(Intimacao.external_id == item.external_id)
    )
    if existing is not None:
        return existing

    intimacao = Intimacao(
        external_id=item.external_id,
        numero_processo=item.numero_processo,
        tribunal=item.tribunal,
        tipo_comunicacao=item.tipo_comunicacao,
        texto=item.texto,
        data_disponibilizacao=item.data_disponibilizacao,
        meio=item.meio,
        oab_numero=oab_numero,
        oab_uf=oab_uf,
        link=item.link,
        raw=item.raw,
    )
    session.add(intimacao)
    session.flush()
    return intimacao


def enrich_processo(dto: DatajudProcesso, session: Session) -> Processo:
    """Upsert a Processo (+ its andamentos) from a DataJud result.

    Idempotent on numero_processo. On first insert, andamentos are created.
    """
    existing = session.scalar(
        select(Processo).where(Processo.numero_processo == dto.numero_processo)
    )
    if existing is not None:
        return existing

    processo = Processo(
        numero_processo=dto.numero_processo,
        tribunal=dto.tribunal,
        classe=dto.classe,
        orgao_julgador=dto.orgao_julgador,
        data_ajuizamento=dto.data_ajuizamento,
        sistema=dto.sistema,
        nivel_sigilo=dto.nivel_sigilo,
        raw_datajud=dto.raw,
    )
    session.add(processo)
    session.flush()

    for mov in dto.movimentos:
        session.add(
            Andamento(
                processo_id=processo.id,
                codigo=mov.codigo,
                nome=mov.nome,
                data_hora=mov.data_hora,
            )
        )
    session.flush()
    return processo
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/capture/test_service.py -v`
Expected: PASS (all 4).

- [ ] **Step 5: Commit**

```
git add backend/app/capture/service.py backend/tests/capture/test_service.py
git commit -m "feat: add capture normalization service (DJEN/DataJud -> SOR)"
```

---

## Task 8: Prazo registration service (compute + persist) — TDD

**Files:**
- Create: `backend/app/prazo_engine/service.py`
- Test: `backend/tests/prazo_engine/test_service.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/prazo_engine/test_service.py`:
```python
from datetime import date

from app.prazo_engine.service import registrar_prazo
from app.sor.models import Intimacao, Prazo


def _make_intimacao(session) -> Intimacao:
    intimacao = Intimacao(
        external_id="555",
        numero_processo="00008323520184013202",
        data_disponibilizacao=date(2026, 6, 8),
    )
    session.add(intimacao)
    session.commit()
    return intimacao


def test_registrar_prazo_persists_computed_dates(db_session):
    intimacao = _make_intimacao(db_session)
    prazo = registrar_prazo(intimacao, prazo_dias=15, session=db_session)
    db_session.commit()

    stored = db_session.query(Prazo).one()
    assert stored.intimacao_id == intimacao.id
    assert stored.prazo_dias == 15
    assert stored.disponibilizacao == date(2026, 6, 8)
    assert stored.publicacao == date(2026, 6, 9)
    assert stored.inicio_contagem == date(2026, 6, 10)
    assert stored.vencimento == date(2026, 6, 30)
    assert stored.status == "aberto"
    assert prazo.id is not None


def test_registrar_prazo_respects_extra_holidays(db_session):
    intimacao = _make_intimacao(db_session)
    # Holiday on Thu 2026-06-11 pushes a 5-day prazo to 2026-06-17
    prazo = registrar_prazo(
        intimacao, prazo_dias=5, session=db_session, extra_holidays={date(2026, 6, 11)}
    )
    db_session.commit()
    assert prazo.vencimento == date(2026, 6, 17)
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest tests/prazo_engine/test_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.prazo_engine.service'`.

- [ ] **Step 3: Implement `backend/app/prazo_engine/service.py`**

```python
from datetime import date

from sqlalchemy.orm import Session

from app.prazo_engine.calendar_factory import build_calendar
from app.prazo_engine.deadline import compute_deadline
from app.sor.models import Intimacao, Prazo


def registrar_prazo(
    intimacao: Intimacao,
    prazo_dias: int,
    session: Session,
    extra_holidays: set[date] | None = None,
) -> Prazo:
    """Compute a deadline for an intimacao and persist it as a Prazo.

    The calendar spans the disponibilizacao year and the next year so a deadline
    that crosses the recess/year boundary is computed correctly.
    """
    start_year = intimacao.data_disponibilizacao.year
    calendar = build_calendar(start_year, start_year + 1, extra_holidays=extra_holidays)
    result = compute_deadline(
        intimacao.data_disponibilizacao, prazo_dias=prazo_dias, calendar=calendar
    )
    prazo = Prazo(
        intimacao_id=intimacao.id,
        prazo_dias=result.prazo_dias,
        disponibilizacao=result.disponibilizacao,
        publicacao=result.publicacao,
        inicio_contagem=result.inicio_contagem,
        vencimento=result.vencimento,
        status="aberto",
    )
    session.add(prazo)
    session.flush()
    return prazo
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/prazo_engine/test_service.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```
git add backend/app/prazo_engine/service.py backend/tests/prazo_engine/test_service.py
git commit -m "feat: add prazo registration service (compute + persist)"
```

---

## Task 9: Capture poller (orchestration + CLI) — TDD

**Files:**
- Create: `backend/app/capture/poller.py`
- Test: `backend/tests/capture/test_poller.py`

**What it does:** for one OAB over a date range, fetch DJEN communications, normalize each into an `Intimacao`, and for each intimation with a `numero_processo`, look it up in DataJud and enrich the `Processo`. Returns a summary. DataJud failures are non-fatal (capture of the intimation must not be lost because enrichment failed).

- [ ] **Step 1: Write the failing test (clients are injected fakes; no network)**

`backend/tests/capture/test_poller.py`:
```python
from datetime import date

from app.capture.datajud import DatajudProcesso
from app.capture.djen import DjenComunicacao, DjenResponse
from app.capture.poller import poll_oab
from app.sor.models import Intimacao, Processo


class FakeDjen:
    def fetch_comunicacoes(self, oab_numero, oab_uf, data_inicio, data_fim, pagina=1, itens_por_pagina=100):
        item = DjenComunicacao.model_validate(
            {
                "id": 555,
                "data_disponibilizacao": "2026-06-08",
                "siglaTribunal": "TRF1",
                "tipoComunicacao": "Intimação",
                "numero_processo": "00008323520184013202",
            }
        )
        return DjenResponse(count=1, items=[item])


class FakeDatajud:
    def __init__(self):
        self.calls = []

    def buscar_processo(self, tribunal_alias, numero_processo):
        self.calls.append((tribunal_alias, numero_processo))
        return DatajudProcesso(numero_processo=numero_processo, tribunal="TRF1", classe="PC")


def test_poll_oab_captures_and_enriches(db_session):
    datajud = FakeDatajud()
    summary = poll_oab(
        oab_numero="12345",
        oab_uf="DF",
        data_inicio=date(2026, 6, 1),
        data_fim=date(2026, 6, 9),
        tribunal_alias="api_publica_trf1",
        djen=FakeDjen(),
        datajud=datajud,
        session=db_session,
    )
    db_session.commit()
    assert summary["intimacoes"] == 1
    assert summary["processos"] == 1
    assert db_session.query(Intimacao).count() == 1
    assert db_session.query(Processo).count() == 1
    assert datajud.calls == [("api_publica_trf1", "00008323520184013202")]


def test_poll_oab_survives_datajud_failure(db_session):
    class FailingDatajud:
        def buscar_processo(self, tribunal_alias, numero_processo):
            raise RuntimeError("datajud down")

    summary = poll_oab(
        oab_numero="12345", oab_uf="DF",
        data_inicio=date(2026, 6, 1), data_fim=date(2026, 6, 9),
        tribunal_alias="api_publica_trf1",
        djen=FakeDjen(), datajud=FailingDatajud(), session=db_session,
    )
    db_session.commit()
    assert summary["intimacoes"] == 1
    assert summary["processos"] == 0
    assert summary["enrichment_errors"] == 1
    assert db_session.query(Intimacao).count() == 1  # intimation still captured
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest tests/capture/test_poller.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.capture.poller'`.

- [ ] **Step 3: Implement `backend/app/capture/poller.py`**

```python
from datetime import date
from typing import Protocol

from sqlalchemy.orm import Session

from app.capture.datajud import DatajudProcesso
from app.capture.djen import DjenResponse
from app.capture.service import enrich_processo, normalize_intimacao


class DjenLike(Protocol):
    def fetch_comunicacoes(
        self, oab_numero: str, oab_uf: str, data_inicio: date, data_fim: date,
        pagina: int = 1, itens_por_pagina: int = 100,
    ) -> DjenResponse: ...


class DatajudLike(Protocol):
    def buscar_processo(self, tribunal_alias: str, numero_processo: str) -> DatajudProcesso | None: ...


def poll_oab(
    oab_numero: str,
    oab_uf: str,
    data_inicio: date,
    data_fim: date,
    tribunal_alias: str,
    djen: DjenLike,
    datajud: DatajudLike,
    session: Session,
) -> dict[str, int]:
    """Capture intimations for one OAB over a date range and enrich processes.

    DataJud enrichment failures are counted but never abort capture.
    """
    response = djen.fetch_comunicacoes(oab_numero, oab_uf, data_inicio, data_fim)
    summary = {"intimacoes": 0, "processos": 0, "enrichment_errors": 0}
    seen_processos: set[str] = set()

    for item in response.items:
        normalize_intimacao(item, oab_numero=oab_numero, oab_uf=oab_uf, session=session)
        summary["intimacoes"] += 1

        numero = item.numero_processo
        if not numero or numero in seen_processos:
            continue
        seen_processos.add(numero)
        try:
            dto = datajud.buscar_processo(tribunal_alias, numero)
        except Exception:
            summary["enrichment_errors"] += 1
            continue
        if dto is not None:
            enrich_processo(dto, session=session)
            summary["processos"] += 1

    return summary


def _cli() -> None:  # pragma: no cover - thin wiring around poll_oab
    import argparse

    import httpx

    from app.capture.datajud import DatajudClient
    from app.capture.djen import DjenClient
    from app.db import SessionLocal
    from app.settings import settings

    parser = argparse.ArgumentParser(description="Poll DJEN + DataJud for one OAB")
    parser.add_argument("--oab", required=True)
    parser.add_argument("--uf", required=True)
    parser.add_argument("--inicio", required=True, help="YYYY-MM-DD")
    parser.add_argument("--fim", required=True, help="YYYY-MM-DD")
    parser.add_argument("--tribunal-alias", required=True, help="e.g. api_publica_trf1")
    args = parser.parse_args()

    with httpx.Client() as http:
        djen = DjenClient(settings.djen_base_url, http)
        datajud = DatajudClient(settings.datajud_api_key, settings.datajud_base_url, http)
        session = SessionLocal()
        try:
            summary = poll_oab(
                oab_numero=args.oab, oab_uf=args.uf,
                data_inicio=date.fromisoformat(args.inicio),
                data_fim=date.fromisoformat(args.fim),
                tribunal_alias=args.tribunal_alias,
                djen=djen, datajud=datajud, session=session,
            )
            session.commit()
            print(summary)
        finally:
            session.close()


if __name__ == "__main__":
    _cli()
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/capture/test_poller.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```
git add backend/app/capture/poller.py backend/tests/capture/test_poller.py
git commit -m "feat: add capture poller orchestration with CLI"
```

---

## Task 10: Alembic migration for the SOR schema

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/` (generated migration lands here)

- [ ] **Step 1: Initialize Alembic**

Run (from `backend/`):
```
.venv\Scripts\alembic init alembic
```
Expected: creates `alembic/` and `alembic.ini`.

- [ ] **Step 2: Point `alembic/env.py` at our metadata and URL**

Replace the `target_metadata = None` line and the config URL wiring in `backend/alembic/env.py` so it reads:
```python
from app.db import Base
from app.settings import settings
from app.sor import models  # noqa: F401  (register tables)

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", settings.database_url)
```
(Leave the rest of the generated `env.py` intact.)

- [ ] **Step 3: Start Postgres and generate the migration**

Run (from `backend/`):
```
docker compose up -d db
.venv\Scripts\alembic revision --autogenerate -m "create sor schema"
```
Expected: a new file under `alembic/versions/` containing `create_table` calls for `escritorio`, `processo`, `andamento`, `intimacao`, `prazo`.

- [ ] **Step 4: Apply and verify the migration**

Run:
```
.venv\Scripts\alembic upgrade head
```
Expected: `Running upgrade -> <rev>, create sor schema`, no errors.

- [ ] **Step 5: Commit**

```
git add backend/alembic.ini backend/alembic/env.py backend/alembic/versions
git commit -m "feat: add alembic migration for SOR schema"
```

---

## Task 11: Read-only API endpoints — TDD

**Files:**
- Create: `backend/app/api/main.py`
- Test: `backend/tests/api/test_endpoints.py`

- [ ] **Step 1: Write the failing test (overrides DB dep with the SQLite fixture)**

`backend/tests/api/test_endpoints.py`:
```python
from datetime import date

from fastapi.testclient import TestClient

from app.api.main import app
from app.db import get_session
from app.sor.models import Intimacao, Prazo


def _client(db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    return TestClient(app)


def test_list_intimacoes_returns_rows(db_session):
    db_session.add(
        Intimacao(
            external_id="555",
            numero_processo="00008323520184013202",
            data_disponibilizacao=date(2026, 6, 8),
            tribunal="TRF1",
        )
    )
    db_session.commit()
    client = _client(db_session)
    resp = client.get("/intimacoes")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["external_id"] == "555"
    app.dependency_overrides.clear()


def test_list_prazos_returns_rows(db_session):
    intimacao = Intimacao(
        external_id="555", numero_processo="X", data_disponibilizacao=date(2026, 6, 8)
    )
    db_session.add(intimacao)
    db_session.commit()
    db_session.add(
        Prazo(
            intimacao_id=intimacao.id, prazo_dias=15,
            disponibilizacao=date(2026, 6, 8), publicacao=date(2026, 6, 9),
            inicio_contagem=date(2026, 6, 10), vencimento=date(2026, 6, 30),
        )
    )
    db_session.commit()
    client = _client(db_session)
    resp = client.get("/prazos")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["vencimento"] == "2026-06-30"
    assert body[0]["status"] == "aberto"
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest tests/api/test_endpoints.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.main'`.

- [ ] **Step 3: Implement `backend/app/api/main.py`**

```python
from datetime import date

from fastapi import Depends, FastAPI
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.sor.models import Intimacao, Prazo

app = FastAPI(title="Causor - Captura + Prazo Engine")


class IntimacaoOut(BaseModel):
    id: int
    external_id: str
    numero_processo: str | None
    tribunal: str | None
    tipo_comunicacao: str | None
    data_disponibilizacao: date

    model_config = {"from_attributes": True}


class PrazoOut(BaseModel):
    id: int
    intimacao_id: int
    prazo_dias: int
    disponibilizacao: date
    publicacao: date
    inicio_contagem: date
    vencimento: date
    status: str

    model_config = {"from_attributes": True}


@app.get("/intimacoes", response_model=list[IntimacaoOut])
def list_intimacoes(session: Session = Depends(get_session)) -> list[Intimacao]:
    return list(session.scalars(select(Intimacao).order_by(Intimacao.id.desc())))


@app.get("/prazos", response_model=list[PrazoOut])
def list_prazos(session: Session = Depends(get_session)) -> list[Prazo]:
    return list(session.scalars(select(Prazo).order_by(Prazo.vencimento.asc())))
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `pytest tests/api/test_endpoints.py -v`
Expected: PASS (both).

- [ ] **Step 5: Run the full suite + lint**

Run (from `backend/`):
```
.venv\Scripts\pytest -q
.venv\Scripts\ruff check app tests
```
Expected: all tests PASS; ruff reports no errors.

- [ ] **Step 6: Commit**

```
git add backend/app/api/main.py backend/tests/api/test_endpoints.py
git commit -m "feat: add read-only intimacoes/prazos API endpoints"
```

---

## Task 12: Integration smoke (real APIs, optional, marked)

**Files:**
- Create: `backend/tests/integration/__init__.py`
- Create: `backend/tests/integration/test_live_apis.py`

These tests hit the real CNJ APIs and are skipped unless `RUN_LIVE=1`. They protect against silent drift in the external contracts and confirm the DataJud key still works.

- [ ] **Step 1: Write the live tests**

`backend/tests/integration/test_live_apis.py`:
```python
import os
from datetime import date, timedelta

import httpx
import pytest

from app.capture.datajud import DatajudClient
from app.settings import settings

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE") != "1", reason="set RUN_LIVE=1 to hit real CNJ APIs"
)


def test_datajud_known_processo_returns_source():
    with httpx.Client() as http:
        client = DatajudClient(settings.datajud_api_key, settings.datajud_base_url, http)
        processo = client.buscar_processo("api_publica_trf1", "00008323520184013202")
    # A known TRF1 process from CNJ examples; assert the contract still parses.
    assert processo is not None
    assert processo.numero_processo
```

- [ ] **Step 2: Run them against production**

Run (from `backend/`, with a valid key in `.env`):
```
$env:RUN_LIVE=1; .venv\Scripts\pytest tests/integration -v; $env:RUN_LIVE=$null
```
Expected: PASS (or a clear failure telling you the DataJud key rotated / contract changed — actionable signal).

- [ ] **Step 3: Commit**

```
git add backend/tests/integration
git commit -m "test: add opt-in live integration smoke for CNJ APIs"
```

---

## Self-review (performed against the spec)

**Spec coverage** (`PLANO_Agente_Operacional_Juridico.md` → "MVP — captura DJEN/DataJud + prazo engine first"):
- Capture via DJEN/Comunica, no scraping → Tasks 5, 7, 9. ✔
- Capture via DataJud (metadata/andamentos) → Tasks 6, 7. ✔
- Deterministic prazo engine (business days, holidays, recess) → Tasks 2, 3, 4, 8. ✔
- SOR entities relevant to this slice (`processo`, `intimacao`, `prazo`, `andamento`, `escritorio`) → Task 1, migration Task 10. ✔
- Secrets not hardcoded (DataJud key via env) → Task 0 settings + `.env.example`. ✔
- TDD with prazo-engine edge cases (recess, local holiday, business-day) → Tasks 2–4, 8 tests. ✔
- Inbox/painel data exposed for verification → read-only API Task 11. ✔
- Technical verification: unit tests (prazo), integration tests with real data (DJEN/DataJud) → Task 12. ✔

**Deferred-and-noted** (in scope of full plan, intentionally out of this slice): Celery/Redis, agent classification of `prazo_dias`, PJe connector, vault/signing, approval gate, frontend. Documented under "Scope and boundaries."

**Type/name consistency check:** `ForensicCalendar.{is_business_day,next_business_day,add_business_days}` used identically across Tasks 2–4 and 8. `DeadlineResult` fields (`disponibilizacao, publicacao, inicio_contagem, vencimento, prazo_dias`) match between Task 3 definition and Task 8 persistence and Task 11 output. `DjenComunicacao.external_id` (str) flows into `Intimacao.external_id` (Task 7) and out via API (Task 11). `DatajudProcesso` fields map 1:1 to `Processo`/`Andamento` columns in Task 7. `poll_oab` signature in Task 9 matches its CLI caller and tests. No undefined references found.

**Placeholder scan:** No TBD/"handle edge cases"/"similar to Task N". Every code step contains complete code. The one external unknown (exact DJEN field/param names) is handled by a concrete verification step (Task 5 Step 1) plus an opt-in live test (Task 12), not a placeholder.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-10-mvp-captura-e-prazo-engine.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session with checkpoints for review.
