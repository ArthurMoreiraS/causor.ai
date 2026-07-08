# Deploy - runbook

Arquitetura de producao: Supabase (Postgres/Auth/Vault), backend FastAPI no
Render e frontend Next.js na Vercel. A topologia completa, o funil de
vendas -> conta e o checklist de corte estao em [`go-live.md`](go-live.md);
este arquivo cobre o passo a passo de subir cada peca.

## 1. Backend

Prerequisito: repo conectado ao provedor e root directory `backend`.

1. Build command: `pip install -e .`
2. Start command: usar o `Procfile`.
3. Rodar migrations no release/startup: `alembic upgrade head`.
4. Variaveis de ambiente:
   - `CAUSOR_DATABASE_URL` = string do Supabase Postgres.
   - `CAUSOR_DATAJUD_API_KEY` = chave DataJud/CNJ.
   - `ANTHROPIC_API_KEY` = chave Claude.
   - `CAUSOR_CLAUDE_CHAT_MODEL` = `claude-haiku-4-5`.
   - `CAUSOR_CLAUDE_CLASSIFICATION_MODEL` = `claude-haiku-4-5`.
   - `CAUSOR_CLAUDE_DRAFT_MODEL` = `claude-sonnet-5`.
   - `CAUSOR_SUPABASE_JWT_SECRET` = segredo HS256 legado ou chave PEM ES256.
   - `CAUSOR_CORS_ORIGINS` = URL final do frontend.
   - `CAUSOR_VAULT_PROVIDER` = `supabase` em producao.

Teste: `GET https://<backend>/health` deve retornar `{"status":"ok"}`.

## 2. Frontend

Root directory `frontend`.

Variaveis:

- `NEXT_PUBLIC_API_BASE` = URL do backend.
- `NEXT_PUBLIC_SUPABASE_URL` = URL do projeto Supabase.
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` = anon key do projeto Supabase.

Depois do deploy, ajuste `CAUSOR_CORS_ORIGINS` no backend para a URL final do
frontend.

## 3. Provisionamento de piloto

A API exige Supabase Auth/JWT. O usuario precisa existir tambem no SOR do
Causor; caso contrario o backend retorna `403 usuario sem acesso`.

1. Crie ou convide o usuario no Supabase Auth.
2. No backend, rode:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli provision-pilot `
  --escritorio "Nome do Escritorio" `
  --nome "Nome do Advogado" `
  --email "advogado@example.com" `
  --oab "123456" `
  --uf "SP"
```

3. O advogado faz login no frontend.
4. Abra `Onboarding` no app e siga o checklist.

## 4. Captura agendada

A primeira captura pode ser feita pelo app em `Captura por OAB`; ela registra a
OAB monitorada e roda a captura imediatamente.

Para rotina agendada, configure um cron externo chamando:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli capture-due
```

O comando tenta novamente falhas transitorias e retorna codigo `1` se alguma
captura falhar definitivamente. Configure o provedor para alertar nesse caso.
Na execucao seguinte, jobs que ficaram `running` alem de
`CAUSOR_JOB_STALE_MINUTES` sao marcados como `failed`.

Variaveis opcionais:

- `CAUSOR_CAPTURE_RETRY_ATTEMPTS` (default `3`);
- `CAUSOR_CAPTURE_RETRY_BACKOFF_SECONDS` (default `2`);
- `CAUSOR_JOB_STALE_MINUTES` (default `60`).

## 5. PJe assistido

No piloto, o protocolo PJe para em `ready_to_sign`; assinatura/envio final
seguem no PJe/PJeOffice e o numero do protocolo e registrado no Causor.

Para capturar sessao PJe assistida em ambiente controlado:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli pje-capture-session `
  --usuario <usuario_id> `
  --tribunal TJSP `
  --url-base "https://pje-treinamento.example/pje"
```

Nao guardar senha, certificado, `.pfx`, chave privada ou OTP no Causor.

## 6. CI

O workflow `.github/workflows/ci.yml` valida backend e frontend em pushes para
`main` e pull requests. Nao publicar uma revisao com CI vermelho.
