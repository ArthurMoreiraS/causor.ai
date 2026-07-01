# Auth (Fase 2) — Login + isolamento multi-tenant — Design

> Data: 2026-06-15. Status: aprovado para virar plano de implementação.
> Decisões já tomadas com o usuário; não re-litigar sem pedir.

## Contexto

Estado atual do código:

- **Sem autenticação.** Todo endpoint da API é aberto; `get_session`
  (`backend/app/sor/db.py`) não tem noção de usuário.
- **Frontend finge o "usuário logado"**: `resolverUsuarioAtual` em
  `frontend/lib/api.ts:325` usa o primeiro usuário do banco e vários endpoints
  recebem `usuario_id`/`escritorio_id` no body do cliente (inseguro).
- **Supabase já é o banco** (Postgres). Logo, **Supabase Auth** é o provedor de
  identidade natural — não reinventar hash de senha nem emissão de JWT.
- `Usuario.email` é único → liga 1:1 com um usuário do Supabase Auth.
- `escritorio_id` já existe em `escritorio`, `usuario`, `cliente`, `processo`,
  `oab_monitorada`, `template_peticao`. **Falta** em `prazo`, `peticao`,
  `intimacao` — hoje o tenant dessas três sai por join no `processo`.

Bloqueio que isto resolve: a API não pode expor dado real de cliente sem auth +
isolamento. Esta é a Fase 2 / passo #1 do `docs/proximos-passos-mvp.md`.

## Objetivo e escopo

**Entregar:** login via Supabase Auth, validação de JWT no backend, e isolamento
de toda query por `escritorio_id` do usuário autenticado.

**Dentro do escopo:**
- Validação de JWT do Supabase no backend (dependency FastAPI).
- Vínculo Supabase user ↔ `Usuario` do SOR.
- Helper central de isolamento por tenant aplicado a todos os endpoints.
- Desnormalização de `escritorio_id` em `prazo`, `peticao`, `intimacao`.
- Login + guard no frontend; remoção do hack `resolverUsuarioAtual`.
- Conta de teste designada a partir do seed atual.

**Fora do escopo (próximas fases):**
- Signup/onboarding self-service (criação de escritório pelo próprio cliente).
- Papéis/roles (admin vs membro) — YAGNI nesta fase; todo usuário do escritório
  tem acesso total ao seu tenant.
- RLS do Postgres (fica como reforço defense-in-depth futuro).
- Verificação de JWT por JWKS assimétrico (evolução futura).

## Decisões travadas

1. **Provedor de identidade:** Supabase Auth.
2. **Isolamento:** nível de aplicação, via helper central de query. RLS depois.
3. **Verificação de JWT:** segredo compartilhado do Supabase (HS256), em
   env/vault, nunca logado.
4. **Tenant das três tabelas:** desnormalizar `escritorio_id` (não join).
5. **Conta de teste:** o escritório/usuário do seed (dados fake) vira o tenant de
   teste designado, com usuário Supabase de mesmo email.
6. **Roles:** deferidos.

## Arquitetura

### 1. Identidade e vínculo Supabase ↔ SOR

- Migração Alembic: adiciona `Usuario.supabase_user_id`
  (`uuid`/`String`, único, nullable).
- O JWT do Supabase traz `sub` (uuid do usuário) e `email`.
- Resolução do usuário a cada request:
  1. casa por `supabase_user_id == sub`;
  2. **claim on first login**: se não achar e o `email` do token bater com um
     `Usuario.email` existente, grava `supabase_user_id = sub` nesse usuário e
     segue;
  3. caso contrário → 403 (usuário autenticado no Supabase mas sem `Usuario` no
     SOR).
- Provisionamento (manual nesta fase): admin/seed cria `Escritorio` + `Usuario`
  (com email) e cria o usuário correspondente no Supabase com o mesmo email.

### 2. Validação de JWT no backend

- Dependency `get_current_user(...) -> CurrentUser` que:
  - lê o header `Authorization: Bearer <token>`;
  - valida assinatura (HS256 com `CAUSOR_SUPABASE_JWT_SECRET`) e `exp`;
  - extrai `sub`/`email`, resolve `Usuario` + `escritorio_id`;
  - retorna `CurrentUser(usuario_id, escritorio_id, email)`.
- Erros:
  - token ausente/ inválido/ expirado → **401**;
  - token válido mas sem `Usuario` correspondente → **403**.
- `/health` continua público. **Todo o resto exige auth.**
- O segredo vive em settings via env (`CAUSOR_SUPABASE_JWT_SECRET`); nunca entra
  em prompt nem em log.

### 3. Isolamento por tenant

- Helper central, ex. `tenant_scope(query, model, current_user)` (ou
  `tenant_query(session, model, current_user)`), que aplica
  `WHERE escritorio_id = :current_escritorio` de forma uniforme.
- Toda **leitura** filtra pelo `escritorio_id` do `CurrentUser`.
- Toda **escrita** carimba `escritorio_id` a partir do `CurrentUser` — o cliente
  deixa de mandar `escritorio_id`/`usuario_id` no body.
- Desnormalização (migração + backfill):
  - adiciona `escritorio_id` em `prazo`, `peticao`, `intimacao`;
  - backfill via join no `processo` para linhas existentes;
  - `intimacao` capturada **sem** processo casado mesmo assim pertence ao
    escritório da OAB monitorada → o `capture` passa a carimbar `escritorio_id`
    na intimação no momento da captura.
- Acesso a um recurso de outro tenant (ex.: `GET /peticoes/{id}` de outro
  escritório) → **404** (não revela existência).

### 4. Frontend

- Cliente `@supabase/supabase-js` faz login (email/senha) e guarda a sessão.
- `request()` em `lib/api.ts` anexa `Authorization: Bearer <access_token>`.
- Remove `resolverUsuarioAtual` e o envio de `usuario_id`/`escritorio_id` no body
  dos endpoints (`editarPeticao`, `aprovarPeticao`, `cumprirPrazo`,
  `revisarPrazo` etc.) — o backend passa a derivar isso do token.
- Tela de login + guard: usuário não autenticado é redirecionado para o login.
- Em 401 vindo da API, limpa sessão e volta ao login.
- Variáveis: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`.

### 5. Conta de teste

- O `seed_demo` continua criando o escritório/usuário fake; este passa a ser o
  **tenant de teste designado**.
- **Credenciais da conta de teste:** email `causorai@gmail.com`, senha
  `senha123`. Cria-se um usuário no Supabase Auth com esse email/senha, e o
  usuário do seed passa a ter `email = causorai@gmail.com` para que o
  "claim on first login" case Supabase ↔ SOR.
- Estas credenciais valem **apenas** para o tenant de teste com dados fake;
  nunca usar para tenant com dado real de cliente (senha fraca e exposta).
- Documentar no runbook (`docs/deploy.md` ou `.env.example`) que esta é conta de
  teste e não deve receber dado real de cliente.

## Modelo de dados — mudanças

- `usuario.supabase_user_id` (uuid/str, único, nullable). Migração Alembic.
- `prazo.escritorio_id`, `peticao.escritorio_id`, `intimacao.escritorio_id`
  (FK para `escritorio.id`). Migração + backfill por join no `processo`.
  `intimacao.escritorio_id` é nullable até o backfill/captura preencher.

## Configuração / env

Backend (`CAUSOR_` prefix):
- `CAUSOR_SUPABASE_JWT_SECRET` — segredo HS256 do projeto Supabase.

Frontend:
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

Atualizar `backend/.env.example` e a doc de deploy. Não commitar segredos.

## Segurança

- Segredo do JWT só em env/vault; nunca logado nem em mensagem de erro.
- Erros de auth genéricos ao cliente (401/403/404 sem detalhe interno).
- Cross-tenant retorna 404, não 403, para não revelar existência de recursos.
- `/health` é o único endpoint público.
- (Carry-over do panorama de segurança, fora do escopo desta fase mas anotado:
  rate-limit nos endpoints de IA e rotação dos segredos colados em chat.)

## Estratégia de testes (TDD)

- `get_current_user`: token válido resolve usuário; ausente/expirado/inválido →
  401; sem `Usuario` correspondente → 403.
- Claim on first login: grava `supabase_user_id` na primeira autenticação por
  email e reusa nas seguintes.
- Isolamento: usuário do escritório A **não** enxerga dados do B em listagens;
  acesso direto a recurso do B → 404.
- Escrita carimba o `escritorio_id` do token (cliente não consegue forjar tenant
  pelo body).
- `/health` permanece acessível sem token.
- Backfill da migração popula `escritorio_id` corretamente via `processo`.

## Plano de rollout

1. Migrações (novas colunas + backfill).
2. Backend: dependency de auth + helper de tenant + aplicar em todos os
   endpoints (TDD).
3. Capture: carimbar `escritorio_id` na intimação.
4. Frontend: login + Bearer + remoção do hack.
5. Criar usuário Supabase de teste para o tenant do seed; validar ponta a ponta.
6. Atualizar `.env.example` e doc de deploy.
