# AGENTS.md

This file provides guidance to AI coding agents (opencode, Claude Code, and
others) when working with code in this repository.

`CLAUDE.md` at the repo root is a thin pointer to this file. Keep the rules
here; do not duplicate them elsewhere.

## Repository status

**2026-09-04 factual correction — read first.** The code review in
[`docs/areas/diagnostico-causor-2026-09-04.md`](docs/areas/diagnostico-causor-2026-09-04.md)
supersedes readiness claims below where they conflict: local-agent read/filing
handlers remain unimplemented. The follow-up execution integrates document
extraction, cited summaries and context construction, with an HTTP end-to-end
test using simulated providers. Passing tests does not establish a live pilot.
Implementation and operational limits are recorded in
[`docs/produto/execucao-2026-09-04.md`](docs/produto/execucao-2026-09-04.md).
Current market findings are in
[`docs/areas/pesquisa-mercado-2026-09-04.md`](docs/areas/pesquisa-mercado-2026-09-04.md).
The founder confirmed solo development and no access to any court system yet.
The founder authorized executing the plan. Internal assisted-flow changes are
implemented; court homologation and legal quality evaluation remain pending.
Preserve the constraints below, but consult the
September diagnosis before relying on older statements of completed workflows.

**MVP with tested components; end-to-end integration incomplete.** The repository
contains the SOR, deterministic deadline engine, DJEN/DataJud capture, Claude
agent layer, FastAPI API, Supabase auth/tenant isolation, Next.js frontend,
templates, persistent jobs, vault adapters and a legacy assisted PJe connector.
The current local-agent handlers do not execute reading or filing. The **MNI
channel** (`connectors/mni/`) has a server-side reader implementation, subject
to credentials and live validation. Upload now runs through extraction,
summarization and context construction in the autos worker. The production
Compose declares that worker; deployment has not been performed in this session.

Two rules that follow from the MNI work and are easy to get wrong:

- **Court-source routing has one owner.** `resolve_capture_fonte` selects MNI
  or the local-agent route per process. Drivers must honor `CourtReaderDriver`;
  the local-agent implementation remains incomplete. Never add a third decision point.
- **Only confirmed MNI endpoints belong in `mni/profiles.py`.** An MNI failure
  marks the capture `failed` and does *not* fall back to the agent, so a guessed
  endpoint sends the lawyer to an error instead of the path that works.

**Market research of 2026-07-29 changed the priority order.** MNI credentialing
is no longer "the single blocker" — it is an *unverified bet*: the MNI is
designed for public bodies (STF's Termo de Adesão, TRF6's institutional
requirements, eproc restricted to Judiciary organs), so a private CNPJ may
simply not be granted access. Evidence and the cheap falsification test are in
[`docs/areas/viabilidade-mercado-2026-07-29.md`](docs/areas/viabilidade-mercado-2026-07-29.md).

The upload route allows an assisted pilot without a new court integration,
once the internal processing gaps are fixed. It does not prove court-file
completeness. Real reading/filing via the local agent requires implementing
and validating the handlers. Current priorities and proposed acceptance tests
are documented in the September diagnosis and evolution plan.

Use `README.md` for repository orientation and `docs/estado.md` as the source
of truth for current status and execution order. The PRD (`docs/produto/PRD.md`)
is strategic; files in `docs/historico/superpowers/` are historical
design/implementation records and must not be used to infer current state.
For market/strategy questions, read `docs/areas/pesquisa-mercado-2026-09-04.md`
first. July/August research preserves historical reasoning, but its claims
about exclusivity, prices and universal access must not be repeated without
current evidence. Jus.br is a candidate channel whose actual capability must
be validated for the selected court; TJTO was a historical pilot, not a newly
confirmed target.

### Build / lint / test (run from `/backend`)

```bash
python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -e ".[dev]"   # setup (Windows venv path)
./.venv/Scripts/python.exe -m pytest -q          # full test suite (TDD)
./.venv/Scripts/python.exe -m ruff check .       # lint
docker compose -f ../infra/docker-compose.yml up -d postgres   # local Postgres + Redis
CAUSOR_DATABASE_URL=postgresql+psycopg://causor:causor@localhost:5432/causor ./.venv/Scripts/alembic.exe upgrade head   # migrate
RUN_LIVE=1 ./.venv/Scripts/python.exe -m pytest tests/test_live_integration.py   # opt-in live CNJ API tests
python -m app.cli poll --oab 12345 --uf SP --escritorio 1       # one capture cycle, bounded window (--dias-janela, default from settings)
python -m app.cli poll --oab 12345 --uf SP --escritorio 1 --historico-completo   # sweeps the OAB's ENTIRE DJEN history — explicit on purpose
```

On Linux/macOS use `.venv/bin/python` / `.venv/bin/alembic` instead of the `Scripts/` paths.

**The current status document is the source of truth.** Read `docs/estado.md`
before making product or architecture decisions.
Decisions already settled with the user (do not re-litigate without being asked):
- Market: Brazil; initial customer: small/medium law firms (solo to ~50 lawyers).
- First workflow: end-to-end case operations — **capture intimation → compute deadline → draft petition → file (protocol)**.
- The moat is **provable execution**, not publication monitoring (a commodity already served by Astrea, Projuris, Legal One, Digesto, Escavador) — and no longer "we file", because doc9/Task.doc9 already runs ~600k automated court operations a month and the OAB's own marketplace (iJUD) sells multi-court filing from R$ 19,90/month. What nobody sells: **completeness proof of the case file + deterministic auditable deadline + immutable trail of human supervision**. Filing is the last mile, executed by the local agent under the lawyer's own credential. See [`docs/areas/viabilidade-mercado-2026-07-29.md`](docs/areas/viabilidade-mercado-2026-07-29.md) and [`docs/areas/modelo-garfield-2026-07-29.md`](docs/areas/modelo-garfield-2026-07-29.md).

## What this product is

A SaaS modeled on Handle.ai but for the Brazilian legal market: AI agents + "computer use" that operate fragmented court portals (PJe, e-SAJ, Projudi, EPROC) and automate the repetitive back-office work (monitoring intimations, tracking deadlines, filing petitions). Missing a deadline is professional malpractice, which makes the pain critical and the ROI measurable.

## Architecture (intended)

Pattern: **System of Record (SOR) + deterministic connectors + agent layer (Claude)**. Do **not** use pure computer-use for every action (slow, expensive, fragile). Use deterministic flows for the known path and Claude for reasoning, normalization, drafting, and exceptions.

Planned backend layout (`/backend`):
- `sor/` — Postgres models + migrations. Core entities: `escritorio`, `usuario`, `cliente`, `processo`, `intimacao/comunicacao`, `prazo`, `peticao`, `andamento`, `documento`, `credencial_assinatura`, `audit_log`.
- `capture/` — consumes **DJEN/Comunica** (intimations) and **DataJud** (process metadata/movements), normalizes, writes to SOR. Polls on schedule by OAB/court. **Capture uses official APIs, never scraping.**
- `prazo_engine/` — **deterministic** deadline calculation (business-day counting per CPC/CLT, national/local holidays, recess/suspensions). This is plain testable code, not an LLM call. Claude only *interprets/classifies* the intimation's content; the date math itself is deterministic.
- `agent/` — Claude orchestration via tool use: extract/classify intimation, decide the applicable petition and draft it, trigger the filing connector, fall back to vision/computer-use for new layouts.
- `connectors/mni/` — SOAP client for the CNJ's **Modelo Nacional de Interoperabilidade**: reads the case file (`consultarProcesso`) and can file (`entregarManifestacaoProcessual`) server-side. Preferred over Playwright wherever the court is credentialed — official, free, standardised. Endpoint profiles are fail-closed and accept **confirmed URLs only**.
- `connectors/pje/` — Playwright, one connector per court system, executed by the **local agent** (never by the hosted backend). The fallback for courts the MNI does not serve. Isolated browser session per lawyer.
- `vault/` — credential/signature storage (cloud certificate reference or encrypted A1). Signing via the cloud-certificate provider's API.
- `queue/` — Celery/RQ workers for async long-running captures and actions.
- `api/` — FastAPI endpoints for the frontend.

Frontend (`/frontend`): Next.js (TypeScript) + React — inbox of intimations, deadline panel (with risk), petition approval queue, per-process timeline/audit, certificate onboarding. Infra (`/infra`): docker-compose, isolated browser workers per tenant.

## Tech stack (intended)

- Backend/agent: Python (FastAPI) + `anthropic` SDK + Playwright (Python).
- Data: PostgreSQL. Queue/cache: Redis + Celery/RQ.
- Frontend: Next.js (TypeScript) + React.
- Deadline engine base: `workalendar` / `python-holidays` for Brazilian holidays.
- Claude models: `claude-haiku-4-5` for chat/classification and `claude-sonnet-5` for drafting. Avoid premium models in the default/test path.

## Non-negotiable constraints

These define the architecture; violating them breaks the product's viability or legality:

1. **Ship what works; custody purism is not a constraint.** Certificates, `.pfx` passwords, and signing/session credentials may be delegated to a trusted third-party vendor (e.g. Escavador, Judit, a cloud-signature provider) for reading the case file or for signing/filing, whenever that is the fastest path to a working flow. There is no rule requiring credentials to stay on the lawyer's machine or inside Causor's own vault — the lawyer cares whether it works, not where the bytes sit. Prefer cloud certificates (BirdID, VIDaaS, Certisign Cloud, SafeID) with API/push signing for convenience; encrypted A1 as fallback; A3 (physical token) stays non-automatable regardless of vendor. Keep secrets out of LLM prompts and application logs — that's leak prevention independent of custody, and still applies no matter who holds the credential.
2. **Human approval gate before any irreversible action (filing/protocol).** The lawyer remains professionally responsible (OAB). Filing must pass a configurable human-approval gate; the gate is disengaged only as confidence grows, never removed from the codebase.
3. **Immutable audit trail from day one.** Every step the agent takes is logged immutably.
4. **Official APIs before scraping.** DJEN/Comunica and DataJud for capture; computer-use/Playwright is for *action* only, with human-in-the-loop fallback when captcha/layout changes block it.

## Working agreements

- **TDD, especially for `prazo_engine`.** Deadline math must have unit tests for edge cases (recess, local holidays, business-day counting) before implementation. Target ≥99% correct deadline calculation on tested cases.
- Each component has a single responsibility and is testable in isolation (see the layout above).
- Build order: MVP vertical slice first (1 court + the single end-to-end flow with the gate), then connector expansion, then additional agents, then multi-tenant/billing/scale. Don't broaden scope ahead of this order without being asked.

## External API references (verified)

- **DataJud (process metadata/movements):** `POST https://api-publica.datajud.cnj.jus.br/api_publica_<tribunal>/_search`, header `Authorization: APIKey <chave pública do CNJ>`, Elasticsearch-style JSON query body. The public key is published on the DataJud Wiki and may be rotated by CNJ — fetch it at runtime/config, never hardcode permanently. Response `_source` fields include `numeroProcesso`, `classe`, `tribunal`, `dataAjuizamento`, `orgaoJulgador`, `sistema`, `movimentos[]`, `assuntos[]`, `nivelSigilo`.
- **DJEN / Comunica (intimations):** `GET https://comunicaapi.pje.jus.br/api/v1/comunicacao` (Swagger at `https://comunicaapi.pje.jus.br/`). Poll by OAB/court. Confirm exact query parameters against the live Swagger before coding the client.
