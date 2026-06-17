# Tela de login no frontend + Supabase — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao app Next.js login por e-mail+senha via Supabase, enviar o token Bearer em todas as chamadas, proteger rotas e permitir definir senha pelo convite.

**Architecture:** Abordagem A (Supabase client-side). Sessão persistida no localStorage pelo SDK; um `AuthProvider` (React context) expõe sessão e redireciona quem não está logado; o `request()` do `lib/api.ts` anexa `Authorization: Bearer <access_token>`. Nenhum cookie/SSR — o app já é 100% client e o backend autentica por header.

**Tech Stack:** Next.js 15 (App Router, client components), React 19, TypeScript, `@supabase/supabase-js`, Vitest (novo, só para o helper puro).

## Global Constraints

- Gerenciador de pacotes do frontend: **pnpm** (há `node_modules/.pnpm`). Onde houver `pnpm`, `npm run` equivale.
- Segredos **nunca** comitados: `frontend/.env.local` e `backend/.env` estão no `.gitignore` (Next ignora `.env*.local`). Commitar apenas `.example`.
- Alias de import `@/` já configurado no `tsconfig.json` (ex.: `@/lib/api`). Use-o para imports de `lib/` e `app/`.
- Backend roda em `http://localhost:8000`; frontend em `http://localhost:3000`. CORS do backend já libera a 3000.
- Algoritmo de JWT esperado pelo backend: **HS256** com segredo compartilhado (`backend/app/auth/jwt_auth.py`). Confirmar no painel Supabase (Task 8).
- Branch de trabalho: `feat/auth-fase2`.

---

### Task 1: Dependência + cliente Supabase + config de ambiente

**Files:**
- Modify: `frontend/package.json` (adicionar dependência)
- Create: `frontend/lib/supabase.ts`
- Create: `frontend/.env.local.example`
- Create: `frontend/.env.local` (NÃO comitar — gitignored)

**Interfaces:**
- Produces: `supabase` (instância de `SupabaseClient`) exportada de `@/lib/supabase`.

- [ ] **Step 1: Instalar o SDK do Supabase**

Run (em `frontend/`):
```bash
pnpm add @supabase/supabase-js
```
Expected: `package.json` passa a listar `@supabase/supabase-js` em `dependencies`.

- [ ] **Step 2: Criar o exemplo de env (comitável)**

Create `frontend/.env.local.example`:
```
# Copie para .env.local e preencha. .env.local está no .gitignore.
NEXT_PUBLIC_SUPABASE_URL=https://ufzrhthkfmlzhaykkfsl.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon/public key do painel Supabase: Project Settings > API > Project API keys > anon public>
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

- [ ] **Step 3: Criar o `.env.local` real (preenchido)**

Create `frontend/.env.local` com os mesmos campos, preenchendo `NEXT_PUBLIC_SUPABASE_ANON_KEY` com a chave anon real do painel. Este arquivo não é comitado.

- [ ] **Step 4: Criar o cliente Supabase singleton**

Create `frontend/lib/supabase.ts`:
```ts
import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  throw new Error(
    "Supabase não configurado: defina NEXT_PUBLIC_SUPABASE_URL e " +
      "NEXT_PUBLIC_SUPABASE_ANON_KEY em frontend/.env.local"
  );
}

export const supabase = createClient(url, anonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    // Necessário para o link de convite/recuperação popular a sessão em /set-password.
    detectSessionInUrl: true
  }
});
```

- [ ] **Step 5: Verificar type-check**

Run (em `frontend/`):
```bash
pnpm exec tsc --noEmit
```
Expected: sem erros relacionados a `lib/supabase.ts`.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/lib/supabase.ts frontend/.env.local.example
git commit -m "feat(auth-fe): adiciona SDK e cliente Supabase no frontend"
```

---

### Task 2: Helper puro `withAuthHeaders` (TDD com Vitest)

**Files:**
- Modify: `frontend/package.json` (devDependency vitest + script `test`)
- Create: `frontend/lib/auth-headers.ts`
- Test: `frontend/lib/auth-headers.test.ts`

**Interfaces:**
- Produces: `withAuthHeaders(base: Record<string, string>, token: string | null | undefined): Record<string, string>`.

- [ ] **Step 1: Instalar o Vitest e adicionar script de teste**

Run (em `frontend/`):
```bash
pnpm add -D vitest
```
Depois, em `frontend/package.json`, adicionar ao bloco `"scripts"`:
```json
"test": "vitest run"
```

- [ ] **Step 2: Escrever o teste que falha**

Create `frontend/lib/auth-headers.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { withAuthHeaders } from "./auth-headers";

describe("withAuthHeaders", () => {
  it("adiciona Authorization quando há token", () => {
    const result = withAuthHeaders({ "Content-Type": "application/json" }, "abc");
    expect(result).toEqual({
      "Content-Type": "application/json",
      Authorization: "Bearer abc"
    });
  });

  it("não adiciona Authorization quando o token é nulo/indefinido", () => {
    expect(withAuthHeaders({ "Content-Type": "application/json" }, null)).toEqual({
      "Content-Type": "application/json"
    });
    expect(withAuthHeaders({ "Content-Type": "application/json" }, undefined)).toEqual({
      "Content-Type": "application/json"
    });
  });
});
```

- [ ] **Step 3: Rodar o teste e ver falhar**

Run (em `frontend/`):
```bash
pnpm test
```
Expected: FAIL — `Failed to resolve import "./auth-headers"` (o módulo ainda não existe).

- [ ] **Step 4: Implementar o helper**

Create `frontend/lib/auth-headers.ts`:
```ts
export function withAuthHeaders(
  base: Record<string, string>,
  token: string | null | undefined
): Record<string, string> {
  if (!token) return base;
  return { ...base, Authorization: `Bearer ${token}` };
}
```

- [ ] **Step 5: Rodar o teste e ver passar**

Run (em `frontend/`):
```bash
pnpm test
```
Expected: PASS — 2 testes passam.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/lib/auth-headers.ts frontend/lib/auth-headers.test.ts
git commit -m "feat(auth-fe): helper withAuthHeaders com teste"
```

---

### Task 3: AuthProvider + hook de guarda + wrap no layout

**Files:**
- Create: `frontend/app/AuthProvider.tsx`
- Modify: `frontend/app/layout.tsx`

**Interfaces:**
- Consumes: `supabase` de `@/lib/supabase`.
- Produces:
  - `AuthProvider` (component) — envolve a árvore.
  - `useAuth(): { session, user, loading, signOut }`.
  - `useRequireAuth(): { session, user, loading, signOut }` — redireciona para `/login` se não houver sessão.

- [ ] **Step 1: Criar o AuthProvider e os hooks**

Create `frontend/app/AuthProvider.tsx`:
```tsx
"use client";

import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import type { Session, User } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";

type AuthState = {
  session: Session | null;
  user: User | null;
  loading: boolean;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  const signOut = async () => {
    await supabase.auth.signOut();
  };

  return (
    <AuthContext.Provider
      value={{ session, user: session?.user ?? null, loading, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth deve ser usado dentro de <AuthProvider>");
  return ctx;
}

export function useRequireAuth(): AuthState {
  const auth = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!auth.loading && !auth.session) {
      router.replace("/login");
    }
  }, [auth.loading, auth.session, router]);
  return auth;
}
```

- [ ] **Step 2: Envolver a árvore no layout**

Modify `frontend/app/layout.tsx` — adicionar o import e envolver `{children}`:
```tsx
import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "./AuthProvider";

export const metadata: Metadata = {
  title: "Causor",
  description: "Agente operacional juridico"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://api.fontshare.com/v2/css?f[]=satoshi@500,700&display=swap"
          rel="stylesheet"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 3: Verificar type-check**

Run (em `frontend/`):
```bash
pnpm exec tsc --noEmit
```
Expected: sem erros.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/AuthProvider.tsx frontend/app/layout.tsx
git commit -m "feat(auth-fe): AuthProvider, useRequireAuth e wrap no layout"
```

---

### Task 4: Anexar token Bearer no `request()` do `lib/api.ts`

**Files:**
- Modify: `frontend/lib/api.ts:195-209` (função `request`) e topo do arquivo (imports).

**Interfaces:**
- Consumes: `supabase` de `./supabase`, `withAuthHeaders` de `./auth-headers`.

- [ ] **Step 1: Adicionar imports no topo do `lib/api.ts`**

No início de `frontend/lib/api.ts` (antes das declarações de `type`), adicionar:
```ts
import { supabase } from "./supabase";
import { withAuthHeaders } from "./auth-headers";
```

- [ ] **Step 2: Reescrever a função `request`**

Substituir o corpo atual de `request` (linhas ~195-209) por:
```ts
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const headers = withAuthHeaders(
    {
      "Content-Type": "application/json",
      ...((init?.headers as Record<string, string>) ?? {})
    },
    token
  );
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    cache: "no-store"
  });
  if (response.status === 401) {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Sessão expirada");
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}
```

- [ ] **Step 3: Verificar type-check**

Run (em `frontend/`):
```bash
pnpm exec tsc --noEmit
```
Expected: sem erros. (`API_BASE` continua definido logo abaixo dos tipos, sem alteração.)

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat(auth-fe): request() envia Authorization Bearer e trata 401"
```

---

### Task 5: Tela de login + estilos de auth

**Files:**
- Create: `frontend/app/login/page.tsx`
- Modify: `frontend/app/globals.css` (append do bloco de estilos auth)

**Interfaces:**
- Consumes: `supabase` de `@/lib/supabase`.

- [ ] **Step 1: Criar a página de login**

Create `frontend/app/login/page.tsx`:
```tsx
"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const { error: signInError } = await supabase.auth.signInWithPassword({
      email,
      password
    });
    setBusy(false);
    if (signInError) {
      setError("E-mail ou senha inválidos.");
      return;
    }
    router.push("/");
  }

  return (
    <div className="authShell">
      <form className="authCard" onSubmit={handleSubmit}>
        <h1 className="authTitle">Causor</h1>
        <p className="authSub">Entre na sua conta</p>
        <label className="authLabel">
          E-mail
          <input
            className="authInput"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </label>
        <label className="authLabel">
          Senha
          <input
            className="authInput"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error && <p className="authError">{error}</p>}
        <button className="authButton" type="submit" disabled={busy}>
          {busy ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Adicionar os estilos de auth ao final do `globals.css`**

Append em `frontend/app/globals.css`:
```css
/* --- Auth (login / set-password) --- */
.authShell {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0b0c0e;
  padding: 24px;
}
.authCard {
  width: 100%;
  max-width: 360px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: #15171b;
  border: 1px solid #23262d;
  border-radius: 14px;
  padding: 32px 28px;
}
.authTitle {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #f5f6f7;
}
.authSub {
  margin: 0 0 8px;
  font-size: 14px;
  color: #9aa0aa;
}
.authLabel {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #c8ccd2;
}
.authInput {
  padding: 10px 12px;
  border-radius: 9px;
  border: 1px solid #2b2f37;
  background: #0f1114;
  color: #f5f6f7;
  font-size: 14px;
  outline: none;
}
.authInput:focus {
  border-color: #4c6fff;
}
.authButton {
  margin-top: 6px;
  padding: 11px 14px;
  border-radius: 9px;
  border: none;
  background: #4c6fff;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.authButton:disabled {
  opacity: 0.6;
  cursor: default;
}
.authError {
  margin: 0;
  font-size: 13px;
  color: #ff6b6b;
}
```

- [ ] **Step 3: Verificar a tela no navegador**

Run o frontend (`pnpm dev`) e abrir `http://localhost:3000/login`.
Expected: card de login renderiza centralizado, campos e-mail/senha e botão "Entrar".

- [ ] **Step 4: Commit**

```bash
git add frontend/app/login/page.tsx frontend/app/globals.css
git commit -m "feat(auth-fe): tela de login e estilos de auth"
```

---

### Task 6: Guarda de rota no dashboard + logout no ProfileModal

**Files:**
- Modify: `frontend/app/page.tsx` (componente `Home`, a partir da linha 111; e `<ProfileModal>` na ~1219)
- Modify: `frontend/app/components/ProfileModal.tsx`

**Interfaces:**
- Consumes: `useRequireAuth` de `@/app/AuthProvider` (ou caminho relativo `./AuthProvider`).
- ProfileModal passa a aceitar `onSignOut: () => void | Promise<void>`.

- [ ] **Step 1: Importar o hook de guarda no `page.tsx`**

No bloco de imports de `frontend/app/page.tsx`, adicionar:
```tsx
import { useRequireAuth } from "./AuthProvider";
```

- [ ] **Step 2: Chamar o hook como PRIMEIRA linha do componente `Home`**

Em `frontend/app/page.tsx`, logo após `export default function Home() {` (linha 111), antes do `const [data, setData] = ...`:
```tsx
  const { loading: authLoading, session, signOut } = useRequireAuth();
```

- [ ] **Step 3: Gate de render imediatamente antes do `return (` principal do `Home`**

Localizar o `return (` de nível superior do componente `Home` (o grande JSX do dashboard) e inserir, imediatamente antes dele:
```tsx
  if (authLoading || !session) {
    return (
      <div className="authShell">
        <p className="authSub">Carregando…</p>
      </div>
    );
  }

```
> Importante: este `if` deve ficar DEPOIS de todos os hooks (`useState`/`useEffect`/`useMemo`) e imediatamente antes do `return (` final — não inserir no meio das declarações de hooks.

- [ ] **Step 4: Passar `onSignOut` ao ProfileModal**

Em `frontend/app/page.tsx` (~linha 1219), trocar:
```tsx
          <ProfileModal onClose={() => setOverlay(null)} />
```
por:
```tsx
          <ProfileModal onClose={() => setOverlay(null)} onSignOut={signOut} />
```

- [ ] **Step 5: Habilitar o botão Sair no ProfileModal**

Substituir todo o conteúdo de `frontend/app/components/ProfileModal.tsx` por:
```tsx
"use client";

import { LogOut, X } from "lucide-react";

export default function ProfileModal({
  onClose,
  onSignOut
}: {
  onClose: () => void;
  onSignOut: () => void | Promise<void>;
}) {
  return (
    <div className="modalOverlay" onClick={onClose}>
      <div className="modalCard settingsCard" onClick={(e) => e.stopPropagation()}>
        <header className="settingsHeader">
          <h3>Conta</h3>
          <button className="iconButton" onClick={onClose} aria-label="Fechar">
            <X size={15} />
          </button>
        </header>
        <div className="profileCard">
          <div className="avatar large">AM</div>
          <div>
            <strong>Sessão ativa</strong>
            <span>Você está autenticado via Supabase.</span>
          </div>
        </div>
        <div className="settingsFooter">
          <button className="toolbarButton" onClick={() => onSignOut()}>
            <LogOut size={14} />
            Sair
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Verificar type-check**

Run (em `frontend/`):
```bash
pnpm exec tsc --noEmit
```
Expected: sem erros.

- [ ] **Step 7: Commit**

```bash
git add frontend/app/page.tsx frontend/app/components/ProfileModal.tsx
git commit -m "feat(auth-fe): guarda de rota no dashboard e logout funcional"
```

---

### Task 7: Página de definir senha (`/set-password`)

**Files:**
- Create: `frontend/app/set-password/page.tsx`

**Interfaces:**
- Consumes: `supabase` de `@/lib/supabase`.

- [ ] **Step 1: Criar a página set-password**

Create `frontend/app/set-password/page.tsx`:
```tsx
"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

export default function SetPasswordPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // O link de convite/recuperação do Supabase abre uma sessão de recovery
    // (detectSessionInUrl=true no cliente). Só liberamos o form quando ela existe.
    supabase.auth.getSession().then(({ data }) => setReady(!!data.session));
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setReady(!!s));
    return () => sub.subscription.unsubscribe();
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const { error: updateError } = await supabase.auth.updateUser({ password });
    setBusy(false);
    if (updateError) {
      setError("Não foi possível definir a senha. O link pode ter expirado.");
      return;
    }
    router.push("/");
  }

  return (
    <div className="authShell">
      <form className="authCard" onSubmit={handleSubmit}>
        <h1 className="authTitle">Causor</h1>
        <p className="authSub">Defina sua senha</p>
        {!ready && (
          <p className="authError">Abra esta página pelo link enviado ao seu e-mail.</p>
        )}
        <label className="authLabel">
          Nova senha
          <input
            className="authInput"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
            disabled={!ready}
          />
        </label>
        {error && <p className="authError">{error}</p>}
        <button className="authButton" type="submit" disabled={busy || !ready}>
          {busy ? "Salvando…" : "Salvar senha"}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Verificar a tela no navegador**

Abrir `http://localhost:3000/set-password` (sem link de convite).
Expected: card "Defina sua senha" com aviso "Abra esta página pelo link enviado ao seu e-mail" e campo desabilitado.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/set-password/page.tsx
git commit -m "feat(auth-fe): página de definir senha (convite/recuperação)"
```

---

### Task 8: Wiring operacional + verificação end-to-end manual

**Files:**
- Modify: `backend/.env` (NÃO comitado — adicionar segredo JWT)

**Sem código novo — passos de configuração e validação manual.**

- [ ] **Step 1: Adicionar o segredo JWT ao backend**

No painel Supabase: **Project Settings → API → JWT Settings**. Confirmar que existe o **"JWT Secret" (HS256/legacy)** e copiá-lo.
Adicionar em `backend/.env`:
```
CAUSOR_SUPABASE_JWT_SECRET=<o segredo HS256 copiado>
```
> **Checkpoint de algoritmo:** se o projeto **não** oferecer o JWT Secret HS256 e usar apenas chaves assimétricas (ES256/JWKS), PARE e sinalize — `backend/app/auth/jwt_auth.py` precisará de um ajuste para validar via JWKS antes de prosseguir. Não improvisar.

- [ ] **Step 2: Garantir banco migrado e seed da demo**

Run (em `backend/`, com o `.env` carregado no ambiente):
```bash
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m app.cli seed-demo
```
> Se `seed-demo` não for um subcomando do CLI, rodar o seed pela função `app.sor.seed_demo.seed_demo` (verificar `app/cli.py`). Expected: escritório "Moreira & Caldas Advogados (Demo)" e a usuária Helena existem no banco.

- [ ] **Step 3: Configurar URLs de redirect no Supabase (para o convite local)**

No painel Supabase: **Authentication → URL Configuration**. Definir, para teste local:
- **Site URL:** `http://localhost:3000/set-password`
- **Redirect URLs:** adicionar `http://localhost:3000/set-password` e `http://localhost:3000`

- [ ] **Step 4: Convidar a conta de teste (Helena)**

No painel Supabase: **Authentication → Users → Invite user** → e-mail `helena.moreira@demo.causor.com.br`.

- [ ] **Step 5: Subir backend e frontend**

Terminal 1 (em `backend/`):
```bash
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```
Terminal 2 (em `frontend/`):
```bash
pnpm dev
```

- [ ] **Step 6: Validar o fluxo end-to-end**

1. Abrir o link do e-mail de convite → cai em `/set-password` → definir senha → redireciona para `/`.
2. Se redirecionar para `/login`, entrar com `helena.moreira@demo.causor.com.br` + a senha definida.
3. Expected: o dashboard carrega com os dados da demo (processos, prazos, minutas), sem 401.
4. Abrir o modal de Conta → clicar **Sair** → deve voltar para `/login`.
5. Tentar abrir `http://localhost:3000/` sem sessão → deve redirecionar para `/login`.

- [ ] **Step 7: Registrar resultado**

Sem commit (nenhum arquivo versionado mudou além do `.env` ignorado). Anotar no PR/descrição que o fluxo foi validado manualmente.

---

## Notas de verificação

- Não há suíte de testes automatizada de UI no frontend (só o teste puro do Task 2). As telas e a integração são validadas manualmente no Task 8, rodando o app — coerente com o estado atual do projeto.
- O backend de auth/tenant já tem cobertura (`tests/test_auth_jwt.py`, `tests/test_tenant_isolation.py`) e não é alterado por este plano.
