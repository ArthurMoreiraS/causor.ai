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
- `http://localhost:8000/review/queue`
- `POST http://localhost:8000/capture/demo`
- `POST http://localhost:8000/capture/oab`

## Frontend

Em outro terminal:

```powershell
cd frontend
pnpm install
pnpm dev
```

App:

- `http://localhost:3000`

O botao `Rodar captura` executa `POST /capture/demo` no ambiente local. A rota e idempotente: a primeira execucao cria a intimacao demo do dia, e as proximas nao duplicam a comunicacao.

## Se a tela abrir sem CSS

Pare o dev server e limpe o cache:

```powershell
Remove-Item -LiteralPath .\.next -Recurse -Force
pnpm dev
```

Nao rode `pnpm build` enquanto `pnpm dev` estiver aberto; isso pode invalidar o `.next` do servidor de desenvolvimento.
