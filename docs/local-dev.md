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
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.cli seed-demo
# Opcional: habilita a geracao de minuta com o Claude. Sem isso, o botao
# "Gerar minuta" responde 503 com mensagem clara (o resto do fluxo funciona).
$env:ANTHROPIC_API_KEY="sk-ant-..."
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

API:

- `http://localhost:8000/health`
- `http://localhost:8000/dashboard/operational`
- `http://localhost:8000/review/queue`
- `POST http://localhost:8000/capture/oab`

Se `alembic upgrade head` falhar com `table escritorio already exists`, seu
SQLite local foi criado antes de o Alembic versionar o schema. Preserve os dados
carimbando a revisao inicial e depois aplique as migrations faltantes:

```powershell
.\.venv\Scripts\python.exe -m alembic stamp 40748db8885f
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.cli seed-demo
```

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

## Captura agendada

Para executar as OABs que estiverem vencidas:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli capture-due
```

Falhas HTTP ou de banco recebem retry exponencial limitado. O comando retorna
codigo `1` se alguma OAB falhar definitivamente, permitindo que cron,
Agendador de Tarefas ou monitor externo disparem um alerta. As configuracoes
ficam em `backend/.env.example`.

Para registrar temporariamente a captura horaria no Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register-local-capture-task.ps1
```

O task `Causor Capture Due` executa `scripts/run-capture-due.ps1` a cada hora.
O computador precisa estar ligado e com o usuario conectado. O log local fica
em `logs/capture-due.log` e nao e versionado.

Para remover o agendamento quando o cron de producao estiver ativo:

```powershell
Unregister-ScheduledTask -TaskName "Causor Capture Due" -Confirm:$false
```

## Se a tela abrir sem CSS

Pare o dev server e limpe o cache:

```powershell
Remove-Item -LiteralPath .\.next -Recurse -Force
pnpm dev
```

Nao rode `pnpm build` enquanto `pnpm dev` estiver aberto; isso pode invalidar o `.next` do servidor de desenvolvimento.
