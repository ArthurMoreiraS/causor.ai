# Rodar o Causor localmente

Guia rápido para subir **backend** (FastAPI), **worker de captura** e **frontend** (Next.js) na sua máquina.
Comandos em **PowerShell** (Windows).

## Pré-requisitos

- **Python 3.12+** e **Node.js 20+** com **pnpm** (`npm i -g pnpm`)
- Os arquivos de ambiente já existem e estão preenchidos:
  - `backend/.env` — DB (Supabase remoto), chaves de API, JWT secret
  - `frontend/.env.local` — URL e chave pública do mesmo projeto Supabase,
    `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000`
- A URL do banco deve começar com `postgresql+psycopg://`, pois este projeto
  instala `psycopg`. O banco configurado foi atualizado, com autorização do
  fundador, para a revisão `b0d6e2f8a4c7` em 25/09. Verifique com
  `alembic current`; não é necessário rodar `upgrade head` novamente.
- A chave `NEXT_PUBLIC_SUPABASE_ANON_KEY` deve ser a chave pública do **mesmo**
  projeto do banco, não texto de exemplo. Ela foi corrigida no `.env.local`
  deste computador em 25/09. Reinicie `pnpm.cmd dev` após mudar o arquivo.
- O login local usa a mesma conta do Supabase Auth. Para os PDFs, o backend local
  ainda usa `localdev`: arquivos ficam no disco desta máquina e uma API remota
  não consegue lê-los. Configure um bucket privado compartilhado antes de usar
  autos reais entre local e produção.
- As migrações atuais não suportam SQLite como substituto: falham na revisão
  `b7d5e9f3a2c1` ao adicionar uma constraint.

---

## 1. Backend — http://localhost:8000

Na pasta `backend/`:

```powershell
cd backend

# (só na primeira vez) criar a venv e instalar as dependências
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"

# Consulte a revisão do banco (somente leitura):
.venv\Scripts\python.exe -m alembic current

# rodar a API (--reload recarrega ao salvar)
.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
```

- Health check: http://localhost:8000/health → `{"status":"ok"}`
- Docs interativas (Swagger): http://localhost:8000/docs

---

## 2. Worker de captura OAB

Em outro terminal, na pasta `backend/`, rode:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli worker
```

O botão Captura por OAB cadastra a OAB e cria um job persistente. Sem este
worker, o job fica aguardando execução; a tela permite acompanhar e verificar
novamente. Com o banco compartilhado, este worker pode consumir jobs da conta
real: use apenas para uma captura que você autorizou, nunca como teste isolado.

---

## 3. Frontend — http://localhost:3000

Em **outro terminal**, na pasta `frontend/`:

```powershell
cd frontend

# (só na primeira vez) instalar dependências
pnpm.cmd install

# rodar o dev server
pnpm.cmd dev
```

Abra http://127.0.0.1:3000/login e entre com a conta habitual.
No PowerShell, `pnpm.ps1` pode ser bloqueado pela política de execução;
`pnpm.cmd` funciona sem alterá-la.

Se o login falhar, confirme que `http://127.0.0.1:8000/health` retorna
`{"status":"ok"}` e reinicie o frontend após qualquer edição de `.env.local`.
O Supabase Auth autentica a senha; a API local valida o token e procura o
usuário no banco. Erro de Auth indica URL/chave pública/conta; `401` em `/me`
indica problema de validação do token; `403` em `/me` indica usuário sem vínculo
no banco. Não coloque senha nem `service_role` no frontend.

---

## 4. Agente local (experimental, sem homologação de leitura/protocolo)

O agente local de tribunal é experimental. Os handlers de leitura e protocolo
autenticados ainda não foram homologados. Ele não é necessário para a captura
OAB via DJEN. Para experimentar o pareamento, gere o código em Configurações →
"Agente local" (expira em 10 minutos) e rode:

```powershell
cd backend
$PAIRING_CODE = "copie-o-codigo-exibido-no-Causor"
.\.venv\Scripts\python.exe -m app.local_agent pair `
  --api http://127.0.0.1:8000 `
  --code $PAIRING_CODE `
  --name "Notebook jurídico"

.\.venv\Scripts\python.exe -m app.local_agent run
```

O token fica no keyring do Windows; o perfil Playwright fica em
`%LOCALAPPDATA%\Causor\profiles` (fora do Git). O pareamento não comprova
execução funcional de leitura ou protocolo judicial.

---

## Observação importante sobre a porta / CORS

O backend aceita, por padrão, chamadas de **`localhost:3000`** e **`127.0.0.1:3000`**.
Se a porta 3000 estiver ocupada, o Next sobe em 3001/3002 e o
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
| Worker de captura | `.venv\Scripts\python.exe -m app.cli worker` | jobs OAB |
| Frontend | `pnpm dev`                                                                        | http://localhost:3000 |
