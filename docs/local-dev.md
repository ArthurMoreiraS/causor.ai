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
# Opcional: habilita a geração de minuta com o Claude. Sem isso, o botao
# "Gerar minuta" responde 503 com mensagem clara (o resto do fluxo funciona).
$env:ANTHROPIC_API_KEY="sk-ant-..."
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

API:

- `http://localhost:8000/health`
- `http://localhost:8000/dashboard/operational`
- `http://localhost:8000/review/queue`
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

O botao `Captura por OAB` executa `POST /capture/oab` e grava somente retornos reais das APIs configuradas.

## Se a tela abrir sem CSS

Pare o dev server e limpe o cache:

```powershell
Remove-Item -LiteralPath .\.next -Recurse -Force
pnpm dev
```

Nao rode `pnpm build` enquanto `pnpm dev` estiver aberto; isso pode invalidar o `.next` do servidor de desenvolvimento.
