# Causor

SaaS para escritórios de advocacia brasileiros. Leva o advogado da publicação
até a minuta revisada:

`captura por OAB → prazo revisável → documentos do caso → contexto com fontes → minuta → revisão humana`

O protocolo judicial está fora do MVP. Estado atual, o que já foi validado e
próximos passos: [docs/estado.md](docs/estado.md).

## Estrutura

- `backend/` — FastAPI, SOR multi-tenant, captura DJEN/DataJud, motor de
  prazos, processamento dos autos, camada Claude e filas persistentes.
- `frontend/` — Next.js + React com Supabase Auth.
- `infra/` — Compose de produção, script de deploy e Postgres local.
- `docs/` — estado, direção de produto, operação e histórico
  ([índice](docs/README.md)).

## Desenvolvimento

Guia completo: [docs/operacao/local-dev.md](docs/operacao/local-dev.md).

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --port 8000
```

```powershell
cd frontend
pnpm.cmd install
pnpm.cmd dev
```

## Qualidade

```powershell
cd backend
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
pnpm.cmd check
pnpm.cmd build
```

`.github/workflows/ci.yml` roda essas verificações (mais PostgreSQL 16/17) em
push e pull request. Push na `main` com CI verde implanta na VPS
([deploy](docs/operacao/deploy.md)).

Agentes de IA: leiam [AGENTS.md](AGENTS.md).
