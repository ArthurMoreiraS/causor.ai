# Próximos passos — rumo ao MVP decente

> Snapshot em 2026-06-13. Decisões já tomadas com o usuário; não re-litigar sem pedir.

## Onde estamos (feito e validado)

- **SOR + prazo engine determinístico** (testado).
- **Captura real**: DJEN (público) + DataJud (chave configurada e validada). Fase 1
  "captura agendada" implementada (modelo `OabMonitorada`, scheduler, CLI
  `monitor-oab`/`capture-due`, endpoints `/capturas/oab`).
- **Assistente de chat no Gemini** (free tier) — validado ao vivo com tool-use
  contra dados reais no Supabase. Drafter/classifier seguem no Claude.
- **Banco em produção (Supabase Postgres)** — migrado e com seed. App roda local
  contra ele.
- **Prontidão de deploy**: CORS via env, `Procfile`, `docs/deploy.md` (runbook
  Render/Railway + Vercel). Frontend builda em produção.
- 125 testes verdes, ruff limpo.

## Chaves/serviços configurados (no `backend/.env`, gitignored)

- `CAUSOR_DATABASE_URL` (Supabase) ✅
- `CAUSOR_DATAJUD_API_KEY` ✅
- `GEMINI_API_KEY` (assistente) ✅
- `ANTHROPIC_API_KEY` ✅ (chave válida, **conta sem créditos** — minuta/draft falha até comprar créditos)

## 🚨 Bloqueio de segurança

A API **não tem autenticação**. Não expor dado real de cliente antes da Fase 2.
Deploy só como **demo com dados fictícios** até lá.

## Próximos passos (ordem recomendada)

| # | Passo | Integração/chave nova? | Status |
|---|---|---|---|
| 🔴 1 | **Auth + multi-tenant** (Supabase Auth): validar JWT no backend, isolar por `escritorio_id`, login no frontend | Não (Supabase já existe) | pendente |
| 🔴 2 | **Minuta funcionando**: comprar créditos Claude **ou** mover drafter p/ Gemini | Não (chaves existem) | pendente |
| 🔴 3 | **Captura agendada em produção**: cron chamando `capture-due` (Render Cron / GitHub Actions) | Não | pendente |
| 🟡 4 | **Notificações de prazo por e-mail** (coração do ROI) | **Sim — Resend ou SendGrid (free tier)** | pendente |
| 🟡 5 | **Onboarding real**: cadastro de escritório/OAB/usuário (sair do seed) | Não | pendente |
| 🟢 6 | **Monitoramento de erros** no app publicado | **Sim — Sentry (free tier)** | pendente |
| 🟢 7 | **Deploy demo** seguindo `docs/deploy.md` (precisa das contas Render/Vercel do usuário, login interativo) | Contas Render + Vercel | pendente |

### Resumo: para um MVP decente só falta **1 API nova essencial** — Resend/SendGrid (e-mail de prazo). O resto é trabalho de código sobre o que já existe.

## Diferencial (Nível 2 — além do MVP decente, é o moat)

| Passo | Depende de |
|---|---|
| **Conector PJe** (Playwright, protocolo autônomo atrás do gate) | Credencial do advogado (vault) + escritório-piloto |
| **Assinatura em nuvem** (BirdID/VIDaaS/Certisign/SafeID) | Conta paga + certificado real do piloto |

## Pendências de higiene

- **Rotacionar segredos** colados no chat: senha do Postgres (Supabase),
  `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`. A chave do DataJud é pública.
- **Sigilo/LGPD**: free tier do Gemini pode usar dados p/ treino — usar tier pago
  para dados reais de cliente.
