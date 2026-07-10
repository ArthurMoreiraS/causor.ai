# Rodar o Causor localmente

Guia rápido para subir **backend** (FastAPI) e **frontend** (Next.js) na sua máquina.
Comandos em **PowerShell** (Windows).

## Pré-requisitos

- **Python 3.12+** e **Node.js 20+** com **pnpm** (`npm i -g pnpm`)
- Os arquivos de ambiente já existem e estão preenchidos:
  - `backend/.env` — DB (Supabase remoto), chaves de API, JWT secret
  - `frontend/.env.local` — URL do Supabase e `NEXT_PUBLIC_API_BASE=http://localhost:8000`
- Não precisa de Postgres local: o banco é o Supabase remoto configurado no `.env`.

---

## 1. Backend — http://localhost:8000

Na pasta `backend/`:

```powershell
cd backend

# (só na primeira vez) criar a venv e instalar as dependências
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"

# rodar a API (--reload recarrega ao salvar)
.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
```

- Health check: http://localhost:8000/health → `{"status":"ok"}`
- Docs interativas (Swagger): http://localhost:8000/docs

---

## 2. Frontend — http://localhost:3000

Em **outro terminal**, na pasta `frontend/`:

```powershell
cd frontend

# (só na primeira vez) instalar dependências
pnpm install

# rodar o dev server
pnpm dev
```

Abra http://localhost:3000 → você cai na tela de login (`/login`).

---

## 3. Agente local (leitura/protocolo autenticados no tribunal)

O backend hospedado **nunca** abre navegador de tribunal. Quem executa
Playwright com a sessão do advogado é o **agente local**, pareado uma vez por
computador. Gere o código em Configurações → "Agente local" (expira em 10
minutos) e rode:

```powershell
cd backend
$PAIRING_CODE = "copie-o-codigo-exibido-no-Causor"
.\.venv\Scripts\python.exe -m app.local_agent pair `
  --api http://127.0.0.1:8000 `
  --code $PAIRING_CODE `
  --name "Notebook jurídico"

.\.venv\Scripts\python.exe -m app.local_agent run
```

O token fica no keyring do Windows; a sessão do tribunal fica no perfil
Playwright em `%LOCALAPPDATA%\Causor\profiles` (fora do Git). Comandos de
leitura/protocolo autenticados só executam com o agente online (`run`).

---

## Observação importante sobre a porta / CORS

O backend só aceita chamadas do frontend rodando em **`localhost:3000`** (é o padrão do
`CAUSOR_CORS_ORIGINS`). Se a porta 3000 estiver ocupada, o Next sobe em 3001/3002 e o
**navegador bloqueia as chamadas à API por CORS**.

Deixe a porta 3000 livre antes de subir o frontend. Para achar/encerrar quem está usando:

```powershell
# ver o PID que está na porta 3000
Get-NetTCPConnection -LocalPort 3000 -State Listen | Select-Object OwningProcess

# encerrar esse PID (troque <PID> pelo número acima)
Stop-Process -Id <PID> -Force
```

> Alternativa: se precisar rodar o frontend noutra porta, adicione essa origem ao
> `CAUSOR_CORS_ORIGINS` no `backend/.env`, ex.:
> `CAUSOR_CORS_ORIGINS=http://localhost:3000,http://localhost:3001`

---

## Resumo

| Serviço  | Comando                                                                          | URL                   |
|----------|----------------------------------------------------------------------------------|-----------------------|
| Backend  | `.venv\Scripts\python.exe -m uvicorn app.api.main:app --port 8000 --reload`       | http://localhost:8000 |
| Frontend | `pnpm dev`                                                                        | http://localhost:3000 |
