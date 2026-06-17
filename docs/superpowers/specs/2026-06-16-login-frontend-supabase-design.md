# Design — Tela de login no frontend integrada ao backend + Supabase

Data: 2026-06-16
Branch: feat/auth-fase2
Status: aprovado (aguardando revisão da spec)

## Objetivo

Dar ao app Next.js uma porta de entrada autenticada. Hoje o backend já exige
`Authorization: Bearer <jwt>` em todos os endpoints (auth + multi-tenant prontos
no branch `feat/auth-fase2`), mas o frontend não envia token nenhum — então o app
recebe 401 em tudo. Esta fatia conecta o frontend ao Supabase Auth e ao backend.

Escopo desta fatia (opção 2 acordada com o usuário):
- Tela de **login** (e-mail + senha).
- Página de **definir senha** (`/set-password`) para o fluxo de convite/recuperação.
- **Envio do token** Bearer em todas as chamadas à API.
- **Proteção de rota** (sem sessão → redireciona para `/login`).
- **Logout**.

Fora de escopo (próximo passo separado): script de provisionamento de
escritório+usuário+convite via linha de comando.

## Decisões já tomadas

- **Método de auth:** e-mail + senha (`supabase.auth.signInWithPassword`). Sem
  signup público — acesso é provisionado pelo admin (convite no Supabase).
- **Onde mora o login:** dentro do app, em `app.<dominio>/login`. A landing
  (`causor-landing`, domínio raiz) permanece estática e pública, no máximo com um
  link "Entrar" apontando para o app.
- **Arquitetura (Abordagem A):** Supabase client-side + guarda de rota no cliente.
  Justificativa: o app já é 100% client (`"use client"` em todo `app/`), e o
  backend autentica por header Bearer (não por cookie). `@supabase/ssr`+middleware
  (Abordagem B) e next-auth (Abordagem C) foram descartados por serem overkill e
  desalinhados com o backend.

## Conta de teste

- **Conta fictícia única (dev e deploy):** **Arthur Santos** —
  **`causorai@gmail.com`**. É o usuário advogado responsável criado pelo
  `backend/app/sor/seed_demo.py` (escritório "Moreira & Caldas Advogados (Demo)").
  Convidá-lo no Supabase + definir senha permite logar e cair direto no escritório
  de demo já populado, exercitando auth + isolamento de tenant. O
  *claim-on-first-login* do backend amarra o usuário Supabase ao `usuario` Arthur
  já existente, pelo e-mail.
- A Helena foi descontinuada como conta de teste a pedido do dono: o seed agora
  nasce com `causorai@gmail.com` / Arthur Santos. Ao subir para hospedagem, o banco
  será limpo mantendo apenas essa conta. O script de provisionamento (próximo passo)
  reusa o mesmo e-mail.

## Componentes

1. **Config / dependências**
   - Instalar `@supabase/supabase-js` no frontend.
   - `frontend/.env.local` (não comitar):
     ```
     NEXT_PUBLIC_SUPABASE_URL=https://ufzrhthkfmlzhaykkfsl.supabase.co
     NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon/public key do painel Supabase>
     NEXT_PUBLIC_API_BASE=http://localhost:8000
     ```
   - `backend/.env`: adicionar `CAUSOR_SUPABASE_JWT_SECRET=<JWT secret HS256>`.

2. **Cliente Supabase** — `frontend/lib/supabase.ts`: instancia única (singleton)
   do client, com persistência de sessão (localStorage, padrão do SDK).

3. **AuthProvider** — `frontend/app/AuthProvider.tsx` (client component): React
   context expondo `session`, `user`, `loading`, `signOut`. Inicializa via
   `supabase.auth.getSession()` e escuta `onAuthStateChange`. Envolve `children`
   no `layout.tsx`.

4. **Guarda de rota** — efeito no topo das rotas protegidas (a começar por
   `page.tsx`): enquanto `loading`, mostra estado neutro; sem sessão, redireciona
   para `/login`. `/login` e `/set-password` ficam fora da guarda.

5. **Tela de login** — `frontend/app/login/page.tsx`: form e-mail+senha →
   `signInWithPassword` → sucesso redireciona para `/`. Trata erro de credencial
   inválida e estado de carregando. Visual no padrão do app (reusa `components/ui`).

6. **Definir senha** — `frontend/app/set-password/page.tsx`: trata a sessão de
   recovery/convite que o Supabase abre ao clicar no link do e-mail; pede nova
   senha → `supabase.auth.updateUser({ password })` → redireciona para `/login`
   (ou direto para `/`).

7. **Envio do token** — alterar `frontend/lib/api.ts` (`request()`): antes do
   `fetch`, obter `supabase.auth.getSession()` e, havendo sessão, anexar
   `Authorization: Bearer <access_token>`. Em resposta 401, limpar sessão e
   redirecionar para `/login`.

8. **Logout** — ação `signOut()` exposta pelo AuthProvider, ligada a um botão no
   header/`ProfileModal`.

## Fluxo end-to-end (teste local)

1. Admin convida `helena.moreira@demo.causor.com.br` no painel Supabase
   (Authentication → Invite user).
2. Helena abre o link do e-mail → `/set-password` → define a senha.
3. Helena loga em `/login` → backend faz *claim-on-first-login* e amarra ao
   `usuario` Helena do seed → app carrega com os dados da demo (isolados por tenant).

## Pré-requisitos operacionais (passos do plano, não código novo)

- **JWT secret no backend:** `CAUSOR_SUPABASE_JWT_SECRET` ausente hoje no `.env`.
  Sem ele, endpoints autenticados respondem 500 "auth não configurado"
  (`backend/app/auth/jwt_auth.py:29`). Obter em Supabase → Project Settings → API →
  JWT Settings → "JWT Secret" (HS256/legacy).
- **Confirmar algoritmo HS256:** o backend decodifica com segredo compartilhado
  (HS256). Se o projeto Supabase oferecer apenas chaves assimétricas (ES256/JWKS),
  incluir ajuste pequeno em `jwt_auth.py` para validar via JWKS. Verificar no
  painel antes de implementar.
- **Banco migrado + seed:** garantir `alembic upgrade head` e `seed_demo` rodados
  no Postgres em uso (Supabase pooler, conforme `backend/.env`), para a Helena
  existir.

## Testes

- `request()` anexa `Authorization: Bearer <token>` quando há sessão; não anexa
  quando não há.
- AuthProvider/guarda redireciona para `/login` quando não há sessão.
- (Backend de auth + tenant já possui cobertura — `test_auth_jwt`,
  `test_tenant_isolation`, etc. — não é alterado nesta fatia.)

## Comandos de execução (dev local)

Backend (porta 8000), a partir de `backend/`:
```
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend (porta 3000), a partir de `frontend/`:
```
pnpm dev    # ou: npm run dev
```

CORS do backend já libera `http://localhost:3000` (`backend/app/settings.py:27`).

## Não-objetivos

- Signup público / self-service.
- Script de provisionamento (escritório+usuário+convite) — próximo passo.
- Migração para `@supabase/ssr`/cookies/SSR.
- Billing, planos, recuperação de senha "esqueci minha senha" autosserviço
  (pode reaproveitar o fluxo de recovery do Supabase depois).
