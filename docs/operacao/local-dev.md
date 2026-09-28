# Desenvolvimento local

> **Quickstart:** para subir o backend e o frontend rapidamente, veja
> [`RODAR-LOCAL.md`](../../RODAR-LOCAL.md) na raiz do repo. Este documento cobre
> o setup completo (primeira instalação), troubleshooting e captura agendada.

O caminho atual usa PostgreSQL. Em 25/09, o fundador autorizou o banco Supabase
compartilhado para desenvolvimento local; ele está na revisão `b0d6e2f8a4c7`.
O `frontend/.env.local` usa uma chave pública validada do mesmo projeto.
Consulte [RODAR-LOCAL.md](../../RODAR-LOCAL.md) para o login e o limite do
armazenamento de PDFs em disco local.

## Uso diario

Com `backend/.env`, `frontend/.env.local`, a venv e as dependencias ja
configuradas, abra três terminais na raiz do repositorio.

Terminal 1:

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli worker
```

O worker consome jobs OAB do banco configurado. No banco compartilhado, só
execute capturas autorizadas; não use jobs reais para testar alterações.

Terminal 3:

```powershell
cd frontend
pnpm.cmd dev
```

Valide `http://localhost:8000/health` e abra `http://localhost:3000`.

## Backend

Para a primeira instalacao, execute na raiz do repositorio:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
# Configure CAUSOR_DATABASE_URL=postgresql+psycopg://... para o banco autorizado.
# Rode upgrade head apenas se a revisão consultada estiver atrás da revisão atual.
.\.venv\Scripts\python.exe -m alembic upgrade head
# Opcional: habilita a geracao de minuta com o Claude. Sem isso, o botao
# "Gerar minuta" responde 503 com mensagem clara (o resto do fluxo funciona).
$env:ANTHROPIC_API_KEY="sk-ant-..."
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

API:

- `http://localhost:8000/health`
- `http://localhost:8000/dashboard/operational`
- `http://localhost:8000/review/queue`
- `POST http://localhost:8000/jobs/capture/oab` (cadastro e enfileiramento)
- `GET http://localhost:8000/jobs/{id}` (acompanhamento)

Não use SQLite para validar as migrações deste checkout: a revisão
`b7d5e9f3a2c1` usa uma alteração de constraint que SQLite não suporta.

## Frontend

Em outro terminal:

```powershell
cd frontend
pnpm.cmd install
pnpm.cmd dev
```

App:

- `http://localhost:3000`

O botão `Captura por OAB` cria um job persistente em `POST /jobs/capture/oab`.
O botão permite fechar o modal e voltar ao acompanhamento. Sem o worker do
segundo terminal, o job permanece aguardando execução. O endpoint síncrono
`POST /capture/oab` permanece disponível para clientes legados.

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
pnpm.cmd dev
```

Nao rode `pnpm build` enquanto `pnpm dev` estiver aberto; isso pode invalidar o `.next` do servidor de desenvolvimento.
