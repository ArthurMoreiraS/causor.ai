# Desenvolvimento local

Comandos em PowerShell (Windows). No Linux/macOS, troque `.venv\Scripts\` por
`.venv/bin/` e `pnpm.cmd` por `pnpm`.

## Pré-requisitos

- Python 3.12+ e Node.js 22+ com pnpm (`npm i -g pnpm`).
- `backend/.env` (copiar de `backend/.env.example`) com banco, chaves de API e
  configuração de Auth. A URL do banco começa com `postgresql+psycopg://`.
- `frontend/.env.local` (copiar de `frontend/.env.local.example`) com URL e
  chave **pública** do mesmo projeto Supabase e
  `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000`. Nunca colocar `service_role`
  ou senha no frontend.
- Tesseract com idioma `por`, se for testar OCR (`CAUSOR_TESSERACT_CMD` aponta
  o executável quando não está no PATH).

## Banco

Duas opções:

- **Postgres local descartável** (recomendado para testar mudanças):
  `docker compose -f infra/docker-compose.yml up -d postgres` e
  `CAUSOR_DATABASE_URL=postgresql+psycopg://causor:causor@localhost:5432/causor`,
  depois `alembic upgrade head`.
- **Supabase compartilhado com produção** (autorizado pelo fundador): use só
  para conferência. Os workers locais consomem jobs reais dessa base, então não
  rode captura ou processamento como teste. Consulte a revisão com
  `alembic current` e só rode `upgrade head` com autorização.

SQLite não serve para validar migrações (a revisão `b7d5e9f3a2c1` altera uma
constraint que ele não suporta). A suíte de testes usa SQLite descartável e
ignora o que depende de PostgreSQL; esses casos rodam no CI.

## Primeira instalação

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env

cd ..\frontend
pnpm.cmd install
```

## Uso diário

Terminal 1 — API (http://127.0.0.1:8000, Swagger em `/docs`):

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2 — worker de jobs (captura OAB, análise de prazos, operações de
trabalho):

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli worker
```

Terminal 3 — frontend (http://127.0.0.1:3000):

```powershell
cd frontend
pnpm.cmd dev
```

Opcionais, conforme o que for testar:

```powershell
.\.venv\Scripts\python.exe -m app.autos.worker        # extração/OCR/resumo dos documentos
.\.venv\Scripts\python.exe -m app.capture.service     # agendador de captura por OAB
```

Sem o worker, a captura por OAB fica "aguardando execução"; a tela permite
acompanhar e verificar de novo. Sem `ANTHROPIC_API_KEY`, as operações com IA
respondem com erro explícito e o resto do fluxo funciona.

## Arquivos dos autos

O `localdev` grava os PDFs em `backend/artifacts/objects`, no disco desta
máquina. A produção não enxerga esses arquivos, e o worker de produção não
processa jobs cujos arquivos estão em outro ambiente. **Não envie autos reais
pelo backend local.** Para compartilhar arquivos entre ambientes seria preciso
um bucket privado (`CAUSOR_OBJECT_STORE_PROVIDER=s3`).

## Problemas comuns

- **Login falha:** confirme `http://127.0.0.1:8000/health` →
  `{"status":"ok"}` e reinicie o frontend depois de editar `.env.local`. Erro no
  Supabase Auth indica URL, chave pública ou conta; `401` em `/me` indica falha
  ao validar o token; `403` em `/me` indica usuário sem vínculo no banco (ver
  [onboarding](onboarding-piloto.md)).
- **CORS:** a API aceita `localhost:3000` e `127.0.0.1:3000`. Se o Next subir em
  outra porta, libere a 3000
  (`Get-NetTCPConnection -LocalPort 3000 -State Listen`) ou adicione a origem em
  `CAUSOR_CORS_ORIGINS`.
- **Tela sem CSS:** pare o dev server, apague `frontend/.next` e rode
  `pnpm.cmd dev`. Não rode `pnpm build` com o dev server aberto.
- **`pnpm.ps1` bloqueado pela política de execução:** use `pnpm.cmd`.
