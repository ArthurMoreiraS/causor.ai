# Deploy — runbook

Arquitetura de produção: **Supabase** (Postgres, já configurado) + **backend**
(FastAPI em Render/Railway) + **frontend** (Next.js na Vercel).

> ⚠️ **Antes de expor publicamente:** a API ainda **não tem autenticação**. Sem
> a Fase 2 (Supabase Auth) ou um gate mínimo, qualquer pessoa com a URL lê/escreve
> os dados. Suba assim apenas como **demo com dados fictícios**; para dados reais
> de cliente, faça a Fase 2 primeiro.

## 1. Backend (Render — exemplo)

Pré-requisito: repo no GitHub (já está) e conta no Render.

1. New → **Web Service** → conecta o repo, root directory `backend`.
2. Build command: `pip install -e .`
3. Start command: vem do `Procfile` (`web:`); o `release:` roda as migrations.
4. **Environment variables** (Settings → Environment):
   - `CAUSOR_DATABASE_URL` = string do Supabase (`postgresql+psycopg://...`)
   - `CAUSOR_DATAJUD_API_KEY` = chave pública do CNJ
   - `GEMINI_API_KEY` = chave do Gemini (assistente)
   - `ANTHROPIC_API_KEY` = chave do Claude (minuta) — opcional sem créditos
   - `CAUSOR_CORS_ORIGINS` = `https://<seu-front>.vercel.app` (ou seu domínio)
5. Deploy. Teste: `GET https://<seu-back>.onrender.com/health` → `{"status":"ok"}`.

(No Railway o fluxo é equivalente: detecta o Procfile; setar as mesmas envs.)

## 2. Frontend (Vercel)

1. Import do repo, root directory `frontend`.
2. Framework: Next.js (auto). Build padrão.
3. **Environment variable**:
   - `NEXT_PUBLIC_API_BASE` = `https://<seu-back>.onrender.com`
4. Deploy. Acesse a URL da Vercel.
5. Volte ao backend e ajuste `CAUSOR_CORS_ORIGINS` para a URL final da Vercel.

## 3. Domínio próprio

- Front: Vercel → Domains → aponta `app.seudominio.com`.
- Back: Render → Custom Domain → `api.seudominio.com`.
- Atualize `NEXT_PUBLIC_API_BASE` e `CAUSOR_CORS_ORIGINS` para os domínios finais.

## 4. Agendamento da captura (opcional)

A captura agendada roda via CLI `capture-due`. Em produção, configure um cron
externo (Render Cron Job / GitHub Actions) chamando o comando no ambiente do
backend. Sem isso, dispare manualmente por `POST /capturas/oab` + cron próprio.
