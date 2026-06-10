# Desenvolvimento local

Este caminho sobe o Causor ponta a ponta sem exigir Postgres local.

## Backend

Execute na raiz do repositorio:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
$env:CAUSOR_DATABASE_URL="sqlite:///./causor_dev.db"
.\.venv\Scripts\python.exe -m app.dev_seed
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

API:

- `http://localhost:8000/health`
- `http://localhost:8000/dashboard/operational`

## Frontend

Em outro terminal:

```powershell
cd frontend
pnpm install
pnpm dev
```

App:

- `http://localhost:3000`

## Se a tela abrir sem CSS

Pare o dev server e limpe o cache:

```powershell
Remove-Item -LiteralPath .\.next -Recurse -Force
pnpm dev
```

Nao rode `pnpm build` enquanto `pnpm dev` estiver aberto; isso pode invalidar o `.next` do servidor de desenvolvimento.
