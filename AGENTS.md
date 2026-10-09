# AGENTS.md

Guidance for AI coding agents (Claude Code, opencode and others) working in this
repository. `CLAUDE.md` is a thin pointer to this file; keep the rules here.

## What Causor is

A SaaS for small and medium Brazilian law firms (solo to ~50 lawyers). The MVP
proves one flow:

**capture an OAB publication (or accept a manual demand) → calculate and review
the deadline → gather the case files → draft with cited evidence → human review.**

Filing (protocolo) is out of scope for now. The founder decided this after the
22/09/2026 legal-advisor meeting: the flow before filing, done well, already
carries most of the perceived value. The local agent and the PJe/Playwright
filing connector were removed on 06/10/2026 for the same reason.

Read before planning:

1. [`docs/estado.md`](docs/estado.md) — what is deployed, what was validated
   for real, and what is next. Source of truth for current status.
2. [`docs/produto/direcao-pos-reuniao-2026-09-25.md`](docs/produto/direcao-pos-reuniao-2026-09-25.md)
   — product direction and execution order.
3. [`docs/mercado/pesquisa-mercado-2026-09-04.md`](docs/mercado/pesquisa-mercado-2026-09-04.md)
   — market, vendors, official APIs. Read before any capture/vendor decision.

`docs/historico/` holds superseded research and deferred tracks (MNI
credentialing, PJe assisted filing, the July PRD). Never infer current state
from it.

## Development workflow

- Read `docs/estado.md` and inspect the current diff before planning. Preserve
  existing user changes, including untracked files.
- For substantial work, record scope, acceptance criteria and verification in
  `docs/desenvolvimento/planos/YYYY-MM-DD-slug.md`. When the work is done and
  `docs/estado.md` reflects it, the plan may be deleted — git keeps it.
- Review the actual diff and test evidence. Always distinguish **local**,
  **simulated**, **deployed** and **live-validated** results.
- Questions and research-only requests do not authorize implementation.
- Push to `main` triggers CI and, on green, an automatic deploy to the VPS.
  Do not push without the founder asking.

## Commands

Backend (run from `backend/`; on Linux/macOS use `.venv/bin/...`):

```bash
python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -e ".[dev]"
./.venv/Scripts/python.exe -m pytest -q          # full suite (TDD)
./.venv/Scripts/python.exe -m ruff check .       # lint
docker compose -f ../infra/docker-compose.yml up -d postgres   # local Postgres
RUN_LIVE=1 ./.venv/Scripts/python.exe -m pytest tests/test_live_integration.py   # opt-in live CNJ APIs
python -m app.cli poll --oab 12345 --uf SP --escritorio 1   # one bounded capture cycle
```

Frontend (run from `frontend/`): `pnpm check` (lint + types + tests) and
`pnpm build`. On Windows PowerShell use `pnpm.cmd`.

Frontend styling: every font size, weight, family and color comes from the
tokens in `frontend/app/styles/tokens.css` (Newsreader for titles of 20px and up, as on
the landing; Inter for the
interface, JetBrains Mono only for CNJ numbers). Use `PageHeader`, the
`.dataTable` subgrid table and the badge classes in `components/ui.tsx` and
`globals.css` instead of new one-off styles. `lib/design-tokens.guard.test.ts`
fails on anything outside the tokens.

Local setup and troubleshooting: [`docs/operacao/local-dev.md`](docs/operacao/local-dev.md).
Production: [`docs/operacao/deploy.md`](docs/operacao/deploy.md).

## Architecture

Pattern: **System of Record + deterministic code + Claude for reasoning.** The
LLM interprets, summarizes and drafts over context the deterministic layer has
already assembled; it never does date math and never calls external systems.

Backend (`backend/app/`, FastAPI + SQLAlchemy + Alembic):

| Package | Responsibility |
|---|---|
| `sor/` | Postgres models (multi-tenant by `escritorio`), permissions, demo seed. |
| `capture/` | DJEN/Comunica publications by OAB, DataJud metadata, persistent scheduler (`capture-scheduler`). |
| `prazo_engine/` | Deterministic deadline math (business days, holidays, recess) and the restricted CPC rule catalog. |
| `autos/` | Manual upload of case files, integrity (SHA-256, PDF validation), extraction/OCR, cited summaries, process context and its fail-closed gate. |
| `agent/` | Claude orchestration: classification, deadline interpretation, evidence analysis, drafting, chat assistant, model routing. |
| `queue/` | Persistent DB-backed jobs and workers (capture, deadline analysis, legal-work operations). |
| `api/` | HTTP endpoints for the frontend. |
| `filing/` | PDF rendering of the draft with the office letterhead, and the approval snapshot. No filing. |
| `connectors/mni/` | Dormant server-side reader for the CNJ MNI. Has no UI; see rules below. |
| `vault/`, `storage/`, `auth/`, `alertas/`, `relatorios/` | Secrets, private object store, Supabase JWT, deadline alerts, OAB dossier. |

Frontend (`frontend/`): Next.js + React + Supabase Auth. Modules: Visão geral,
Tarefas, Intimações, Prazos, Clientes, Processos, Documentos, Assistente,
Trabalhos, Minutas, Modelos, Revisão e aprovação, Histórico, Configuração.

Infra: VPS (Hostinger) running Docker Compose with five services — `backend`,
`worker`, `autos-worker`, `capture-scheduler`, `frontend` — behind a shared
Caddy. Database and Auth are a managed Supabase project (Free plan).

LLM models: `claude-haiku-4-5` for chat, classification and default document
summaries; `claude-sonnet-5-5` for evidence analysis, drafting and the explicit
deep summary. Avoid premium models in the default/test path. Details:
[`docs/operacao/modelos-llm.md`](docs/operacao/modelos-llm.md).

## Non-negotiable constraints

1. **Deadlines are deterministic and reviewable.** Date math lives in
   `prazo_engine` with unit tests for every edge case (TDD, target ≥99% on
   tested cases). The LLM may only interpret the publication text. Never
   invent a due date. An automatically calculated deadline is in force without
   confirmation (review is optional). An uncertain case gets a **triage date**
   (5 business days, CPC art. 218 § 3; 2 in criminal cases), always labelled
   "prazo real não identificado" and never presented as the act's deadline
   (founder decision, 07/10/2026).
2. **Human review before anything leaves Causor.** The lawyer is professionally
   responsible. A draft is approved by a person; if filing returns later, it
   goes behind a configurable human-approval gate that is never removed.
3. **Immutable audit trail.** Every relevant mutation and agent step is logged
   append-only.
4. **Official APIs before scraping.** DJEN/Comunica and DataJud for capture.
   Buying case files from a vendor (Judit, Escavador, etc.) is allowed and must
   be measured against a manual inventory before it is promised.
5. **Secrets out of prompts and logs.** Credential custody may be delegated to a
   trusted vendor when that is the fastest working path; leak prevention still
   applies regardless of who holds the credential.
6. **No unproven claims.** Do not claim court-file completeness, coverage or
   competitive exclusivity without evidence. A captured publication is not the
   full case file.

## MNI rules (dormant code, easy to get wrong)

- **Capture routing has one owner:** `autos.service.resolve_capture_fonte`. It
  returns `"mni"` only when the route has a confirmed profile *and* an active
  credential; otherwise automatic capture is refused (`sem_canal_automatico`)
  and the lawyer uploads the files. Never add a second decision point.
- **Only confirmed MNI endpoints belong in `connectors/mni/profiles.py`.** An
  MNI failure marks the capture `failed` with no fallback, so a guessed
  endpoint sends the lawyer to an error.

## Settled decisions (do not re-litigate unless asked)

- Market: Brazil; customer: small/medium law firms.
- First value to prove: the flow above, measured on one authorized real case
  with a lawyer reviewer (time saved, material errors), then five cases.
- Manual upload is the case-file route for the MVP. Automatic collection is
  evaluated afterwards by comparing a vendor route document-by-document against
  that case's manual inventory.
- Filing, PJe-specific automation and the local agent are deferred. PJe is one
  court system among several, never a universal route.
- The founder works solo and has no court-system access yet.

## External API references (verified)

- **DataJud:** `POST https://api-publica.datajud.cnj.jus.br/api_publica_<tribunal>/_search`,
  header `Authorization: APIKey <chave pública do CNJ>`, Elasticsearch-style
  body. The public key is published on the DataJud Wiki and may rotate — keep
  it in configuration. `_source` includes `numeroProcesso`, `classe`,
  `tribunal`, `dataAjuizamento`, `orgaoJulgador`, `sistema`, `movimentos[]`,
  `assuntos[]`, `nivelSigilo`. Metadata only, not the file contents.
- **DJEN / Comunica:** `GET https://comunicaapi.pje.jus.br/api/v1/comunicacao`
  (Swagger at `https://comunicaapi.pje.jus.br/`). Confirm parameters against the
  live Swagger before changing the client.
