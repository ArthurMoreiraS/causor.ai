# Deploy do Causor na VPS — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publicar backend (FastAPI) e frontend (Next.js) do Causor na VPS Hostinger com HTTPS válido e deploy automático a cada push na `main`.

**Architecture:** Docker Compose numa rede interna própria + a rede externa `edge` já usada por outros stacks na VPS. **Não sobe Caddy próprio** — o Causor se pluga no Caddy já existente do stack `infolex-evo` (achado do inventário de 2026-07-28, ver `DEPLOY-VPS.md` §2.1). Imagens são buildadas no GitHub Actions e publicadas privadas no ghcr.io; a VPS só baixa e sobe. Banco e Auth continuam no Supabase remoto — a VPS não hospeda Postgres nem Redis.

**Tech Stack:** Docker + Docker Compose, Caddy 2 (instância já existente, compartilhada), GitHub Actions, ghcr.io, Python 3.12/FastAPI, Next.js 15 (standalone), Supabase (Postgres+Auth) remoto.

**Design de referência:** [`DEPLOY-VPS.md`](../../../DEPLOY-VPS.md) (raiz do repo).

## Global Constraints

- **Domínio:** `app.causorai.com` = frontend, `api.causorai.com` = backend. IP da VPS: `179.197.70.156`.
- **Repositório GitHub:** `ArthurMoreiraS/causor.ai`. Owner do ghcr (minúsculo): `arthurmoreiras`. Imagens: `ghcr.io/arthurmoreiras/causor-backend` e `ghcr.io/arthurmoreiras/causor-frontend`.
- **Backend hospedado NUNCA abre navegador.** Instalar o pacote Python `playwright`, mas **nunca** rodar `playwright install` (browsers) na imagem.
- **Backend precisa de Tesseract** (`tesseract-ocr` + `tesseract-ocr-por`) para o OCR do `process-autos-due`.
- **Segredos só no `.env` da VPS** — nunca no git, nunca embutidos na imagem. As `NEXT_PUBLIC_*` são públicas por design e entram como build args.
- **Banco:** Supabase remoto (`CAUSOR_DATABASE_URL`). Sem Postgres/Redis na VPS.
- **`CAUSOR_FILING_MODE=sandbox`** em produção até haver protocolo real de piloto (o gate de aprovação humana permanece).
- **Portas 80/443 já ocupadas** por `infolex-evo-caddy-1` (stack de terceiro, produção — cliente Infolex). O Causor **não publica porta nenhuma no host**; `causor-backend`/`causor-frontend` só entram na rede interna do Compose + na rede externa `edge`, onde o Caddy existente já os alcança por nome de container.
- **Editar o Caddyfile compartilhado (`/opt/infolex-evo/Caddyfile`) exige backup antes e `caddy reload` depois** — nunca `docker restart` (evita downtime em `evo.infolex.adv.br`/`evo.operlyapp.com`, produção de terceiro).
- **Docker já está instalado na VPS** (usado pelos stacks existentes) — não precisa instalar, só garantir que o usuário `deploy` está no grupo `docker`.
- Prefixo de env do backend é `CAUSOR_` (pydantic-settings). O SDK Anthropic lê `ANTHROPIC_API_KEY` direto do ambiente.

## Legenda de execução

Cada step é marcado com quem executa:
- 🤖 = Claude roda via terminal (SSH/Bash/Actions).
- 👤 = **Arthur** faz manualmente (painel Hostinger, registrador DNS, painel Supabase, GitHub Secrets) — Claude não tem acesso a esses painéis.

---

## Task 1: Acesso SSH, snapshot e inventário da VPS

Estabelecer acesso SSH não-interativo por chave, tirar um snapshot de segurança e descobrir o que já roda na VPS **antes de mexer em qualquer coisa**.

**Files:**
- Create: `C:\Users\moura\AppData\Local\Temp\claude\...\scratchpad\causor_deploy` (par de chaves SSH, fora do repo)
- Create: `docs/superpowers/notes/2026-07-27-vps-inventario.md` (registro do inventário)

- [x] **Step 1 (🤖): Gerar par de chaves SSH dedicado ao deploy** — feito. Chave em `~/.ssh/causor_deploy` (privada, só nesta máquina) / `causor_deploy.pub`.

- [x] **Step 2 (👤): Snapshot da VPS** — feito no painel Hostinger.

- [x] **Step 3 (👤): Autorizar a chave pública no servidor** — feito via painel Hostinger (Chave SSH → Gerenciar).

- [x] **Step 4 (🤖): Testar SSH não-interativo como root** — confirmado: `hostname`/`whoami`/`os-release` retornaram `srv1825391`, `root`, `Ubuntu 24.04.4 LTS` sem prompt de senha.

- [x] **Step 5 (🤖): Inventariar o que já roda (somente leitura)** — feito. Resultado real:
  - **Docker já instalado**, dois stacks já rodando: `infolex-evo` (Evolution API/WhatsApp do cliente Infolex + Postgres + Redis + **Caddy publicando 80/443**) e `operly-evo` (Evolution API/WhatsApp do Operly + Postgres + Redis, sem porta publicada).
  - **Portas 80/443 ocupadas** pelo `infolex-evo-caddy-1`, que roteia por uma **rede Docker externa `edge`** já compartilhada entre os dois stacks (o Caddyfile já tem uma entrada para `evo.operlyapp.com` apontando pro stack Operly).
  - RAM: 3915 MB total, ~1 GB em uso pelos stacks existentes, **~1.4-2.9 GB disponíveis**. Disco: 6.4 GB usados de 48 GB.
  - Sem crontab root, sem outro Nginx/Apache/Caddy fora do Docker, sem conflito de nome/porta com o que o Causor precisa.

- [x] **Step 6 (🤖): Decisão sobre o proxy — tomada com o Arthur**

Como **já há um proxy** (Caddy do `infolex-evo`) nas portas 80/443, a Task 8 original (Caddy próprio do Causor) foi descartada. Decisão registrada em `DEPLOY-VPS.md` §2.1: o Causor entra na rede `edge` existente; o Caddyfile compartilhado ganha duas entradas novas (`app.causorai.com`, `api.causorai.com`); sem Caddy próprio, sem conflito de porta. Isso é refletido nas Tasks 5, 7 e 8 abaixo (revisadas).

- [ ] **Step 7 (🤖): Registrar o inventário em nota própria e commitar**

Escrever `docs/superpowers/notes/2026-07-27-vps-inventario.md` com o resumo do Step 5 (stacks existentes, portas, RAM/disco, decisão do Step 6), depois:
```bash
git add docs/superpowers/notes/2026-07-27-vps-inventario.md DEPLOY-VPS.md docs/superpowers/plans/2026-07-27-deploy-vps.md
git commit -m "docs: inventario da VPS e revisao do design para reusar Caddy/rede edge existentes"
```

**Deliverable:** SSH por chave funcionando não-interativo; snapshot criado; sabemos o que roda na VPS e a estratégia de integração com o proxy existente está decidida e documentada.

---

## Task 2: Hardening e usuário de deploy

Endurecer o acesso (a caixa está com root por senha e sem firewall configurado) e criar um usuário `deploy` não-root. **Docker já está instalado** (usado pelos stacks `infolex-evo`/`operly-evo`) — só falta colocar `deploy` no grupo `docker`.

**Files:** (nenhum no repo — mudanças no servidor)

**Interfaces:**
- Produces: usuário `deploy` com Docker (grupo existente) e sudo; SSH só por chave nas portas 22/80/443.

- [x] **Step 1 (🤖): Criar usuário `deploy` com a mesma chave** — feito, `adduser` + `authorized_keys` copiado + sudo NOPASSWD.

- [x] **Step 2 (🤖): Testar login como `deploy`** — confirmado, `deploy` + `sudo-ok`.

- [x] **Step 3 (🤖): Confirmar Docker existente e colocar `deploy` no grupo** — Docker já instalado (roda `infolex-evo`/`operly-evo`); `deploy` adicionado ao grupo `docker`.

- [x] **Step 4 (🤖): Firewall ufw — só 22/80/443** — `ufw` ativo, `Status: active`, 22/80/443 (v4 e v6) permitidos. Confirmado que os stacks existentes (`infolex-evo`, `operly-evo`) continuaram `Up` depois de ativar.

- [ ] **Step 5 (👤): Firewall da Hostinger**

Painel Hostinger → VPS → **Regras de firewall** (hoje 0) → liberar entrada TCP **22, 80, 443**, bloquear o resto. (Camada extra além do ufw — ainda pendente, ação do Arthur no painel.)

- [x] **Step 6 (🤖): Endurecer o SSH — só chave, sem root direto**

Feito, com uma pegadinha real encontrada: editar `/etc/ssh/sshd_config` não bastou — o Ubuntu 24.04 da Hostinger inclui `/etc/ssh/sshd_config.d/*.conf` **antes** do arquivo principal, e `50-cloud-init.conf` (gerado pelo cloud-init) reafirmava `PasswordAuthentication yes`, vencendo por ordem alfabética sobre o `60-cloudimg-settings.conf` que já dizia `no`. Correção aplicada nesse arquivo específico:
```bash
sudo sed -i "s/^PasswordAuthentication yes/PasswordAuthentication no/" /etc/ssh/sshd_config.d/50-cloud-init.conf
sudo systemctl reload ssh
```
**Nota para o futuro:** se a VPS for reprovisionada ou o cloud-init rodar de novo, esse arquivo pode ser regenerado com `yes` — vale checar `sudo sshd -T | grep passwordauthentication` depois de qualquer reset/rebuild do servidor.

- [x] **Step 7 (🤖): Verificar que senha foi desabilitada** — confirmado via `sudo sshd -T`: `passwordauthentication no`, `permitrootlogin without-password`. Acesso por chave (root e deploy) testado e funcionando depois da mudança.

**Deliverable:** VPS endurecida (chave-only, firewall ufw ativo) com usuário `deploy` no grupo docker. Falta só o Step 5 (firewall do painel Hostinger, ação do Arthur).

---

## Task 3: Dockerfile do backend

Imagem de produção do backend, com Tesseract e sem browsers do Playwright.

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`

**Interfaces:**
- Produces: imagem que roda `python -m uvicorn app.api.main:app`, `python -m app.cli <cmd>` e `python -m alembic upgrade head`. Working dir `/app`; artefatos em `/app/artifacts`.

- [x] **Step 1: Criar `backend/.dockerignore`**

```
.venv/
__pycache__/
*.pyc
tests/
artifacts/
shots/
causor_dev.db
.env
.env.*
.pytest_cache/
.ruff_cache/
```

- [x] **Step 2: Criar `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Tesseract (OCR pt) para process-autos-due. Sem browsers do Playwright:
# o backend hospedado nunca abre navegador (ver Global Constraints).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependencias + o pacote 'app' a partir do pyproject.
COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY alembic ./alembic
RUN pip install .

# Diretorio de artefatos (autos) — montado como volume no Compose.
RUN mkdir -p /app/artifacts

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [x] **Step 3: Buildar a imagem** — Docker local (Windows) não tinha o daemon rodando; build feito diretamente na VPS (ambiente Linux real, mais fiel à produção): contexto do build transferido via `scp`, `docker build -t causor-backend:test .` concluído em ~35s sem erro.

- [x] **Step 4: Smoke test do `/health` (sem banco)** — rodado na VPS: `docker run ... causor-backend:test` respondeu `{"status":"ok"}` em `GET /health`. Container e imagem de teste removidos depois (`docker rm -f`, `docker rmi`).

- [ ] **Step 5: Commit**

```bash
git add backend/Dockerfile backend/.dockerignore
git commit -m "build(backend): Dockerfile de producao com Tesseract, sem browsers Playwright"
```

**Deliverable:** imagem do backend que builda e responde `/health`.

---

## Task 4: Dockerfile do frontend (Next.js standalone)

Imagem enxuta do Next.js usando saída `standalone`.

**Files:**
- Modify: `frontend/next.config.mjs`
- Create: `frontend/Dockerfile`
- Create: `frontend/.dockerignore`

**Interfaces:**
- Consumes (build args): `NEXT_PUBLIC_API_BASE`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
- Produces: imagem que roda `node server.js` na porta 3000.

- [x] **Step 1: Ativar saída standalone em `frontend/next.config.mjs`**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
};

export default nextConfig;
```

- [x] **Step 2: Criar `frontend/.dockerignore`**

```
node_modules/
.next/
.env.local
.env
npm-debug.log
```

- [x] **Step 3: Criar `frontend/Dockerfile`** — versão final abaixo já incorpora os dois ajustes descobertos no build real (Step 4).

```dockerfile
# --- deps ---
FROM node:22-alpine AS deps
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

# --- build ---
FROM node:22-alpine AS build
WORKDIR /app
RUN corepack enable
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_BASE
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE \
    NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY
RUN pnpm build

# --- runtime ---
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

- [x] **Step 4: Buildar a imagem com build args reais** — feito na VPS (Docker local sem daemon ativo), dois problemas reais encontrados e corrigidos no `Dockerfile`:
  1. `node:20-alpine` não bastava: `pnpm@11.2.2` (fixado no `package.json`) exige **Node ≥22.13** — o build falhava em `pnpm install` com `ERR_UNKNOWN_BUILTIN_MODULE: node:sqlite`. Trocado para `node:22-alpine` nos três estágios.
  2. Com Node 22, `pnpm install --frozen-lockfile` ainda falhava com `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH`: o repo tem um `pnpm-workspace.yaml` com `overrides: postcss: 8.5.10`, e o estágio `deps` só copiava `package.json`/`pnpm-lock.yaml` — sem o workspace file, o pnpm não via o override que o lockfile esperava. Corrigido copiando `pnpm-workspace.yaml` também.

  Depois dos dois ajustes: build completo em ~110s, `next build` gerou as 5 rotas (`/`, `/login`, `/set-password`, etc.) sem erro.

- [x] **Step 5: Smoke test** — `GET /login` no container retornou `HTTP 200`.

- [ ] **Step 6: Commit**

```bash
git add frontend/next.config.mjs frontend/Dockerfile frontend/.dockerignore
git commit -m "build(frontend): Dockerfile standalone Next.js com NEXT_PUBLIC build args"
```

**Deliverable:** imagem do frontend que builda e serve `/login`.

---

## Task 5: Compose de produção e `.env` de exemplo (sem Caddy próprio)

Orquestração dos serviços do Causor. **Sem Caddy nesta task** — o TLS/proxy é o Caddy já existente do stack `infolex-evo` (ver `DEPLOY-VPS.md` §2.1); os containers do Causor só precisam de um `container_name` estável e entrar na rede externa `edge` para o Caddyfile compartilhado conseguir apontar para eles (Task 8).

**Files:**
- Create: `infra/docker-compose.prod.yml`
- Create: `infra/.env.prod.example`

**Interfaces:**
- Consumes: imagens `ghcr.io/arthurmoreiras/causor-backend` e `causor-frontend` (Tasks 3, 4, 6); variável `IMAGE_TAG`; rede Docker externa `edge` (já existe na VPS, criada pelo stack `infolex-evo`).
- Produces: containers nomeados `causor-backend` e `causor-frontend`, alcançáveis por esse nome dentro da rede `edge` — é o nome que o Caddyfile compartilhado vai usar (Task 8).

- [ ] **Step 1: Criar `infra/docker-compose.prod.yml`**

```yaml
name: causor

services:
  backend:
    container_name: causor-backend
    image: ghcr.io/arthurmoreiras/causor-backend:${IMAGE_TAG:-latest}
    restart: unless-stopped
    env_file: [.env]
    command: python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000
    volumes:
      - causor_artifacts:/app/artifacts
    networks: [causor, edge]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 5s
      retries: 3

  worker:
    container_name: causor-worker
    image: ghcr.io/arthurmoreiras/causor-backend:${IMAGE_TAG:-latest}
    restart: unless-stopped
    env_file: [.env]
    command: python -m app.cli worker
    volumes:
      - causor_artifacts:/app/artifacts
    networks: [causor]

  frontend:
    container_name: causor-frontend
    image: ghcr.io/arthurmoreiras/causor-frontend:${IMAGE_TAG:-latest}
    restart: unless-stopped
    networks: [causor, edge]

  # One-shot: roda no deploy via `docker compose run --rm migrate`.
  # profile "tools" evita que suba junto com `up -d`.
  migrate:
    image: ghcr.io/arthurmoreiras/causor-backend:${IMAGE_TAG:-latest}
    env_file: [.env]
    command: python -m alembic upgrade head
    restart: "no"
    profiles: ["tools"]
    networks: [causor]

networks:
  causor: {}
  edge:
    external: true

volumes:
  causor_artifacts: {}
```

Note: `edge: external: true` assume que a rede já existe na VPS (criada pelo `infolex-evo`, confirmado no inventário). Se o Compose reclamar que a rede não existe ao rodar localmente/CI (onde `edge` não existe), isso é esperado — `docker compose config` (Step 4 abaixo) ainda valida a sintaxe sem precisar da rede existir.

- [ ] **Step 2: Criar `infra/.env.prod.example`**

```bash
# Copie para /opt/causor/.env na VPS e preencha com os valores reais
# (reutilize os que ja funcionam no backend/.env local). NUNCA comite este .env.

# Tag da imagem a rodar (o deploy do Actions sobrescreve com o SHA do commit).
IMAGE_TAG=latest

# --- Banco: Supabase remoto (mesmo do backend/.env local) ---
CAUSOR_DATABASE_URL=postgresql+psycopg://postgres.<ref>:<senha-url-encoded>@aws-1-<region>.pooler.supabase.com:6543/postgres

# --- Auth Supabase ---
CAUSOR_SUPABASE_JWT_SECRET=

# --- CORS: origem publica do frontend ---
CAUSOR_CORS_ORIGINS=https://app.causorai.com

# --- APIs externas ---
CAUSOR_DATAJUD_API_KEY=
ANTHROPIC_API_KEY=

# --- Producao ---
CAUSOR_VAULT_PROVIDER=supabase
CAUSOR_FILING_MODE=sandbox
CAUSOR_OBJECT_STORE_PROVIDER=localdev
CAUSOR_OBJECT_STORE_LOCAL_PATH=/app/artifacts/objects
```

- [ ] **Step 3: Validar a sintaxe do Compose**

Localmente a rede `edge` não existe, então `config` pode avisar sobre isso — o que importa é não ter erro de sintaxe:
Run: `docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod.example config`
Expected: imprime a config resolvida sem erro de sintaxe (pode listar `edge` como rede externa não resolvida localmente — normal, ela existe na VPS).

- [ ] **Step 4: Commit**

```bash
git add infra/docker-compose.prod.yml infra/.env.prod.example
git commit -m "infra: compose de producao do Causor (sem Caddy proprio, usa rede edge existente)"
```

**Deliverable:** arquivos de orquestração válidos e versionados.

> **Nota (persistência dos autos):** o `causor_artifacts` é um volume Docker, então os documentos capturados sobrevivem a redeploys. Migrar para Supabase Storage (`CAUSOR_OBJECT_STORE_PROVIDER=s3`) fica como productização futura (fora de escopo agora).

---

## Task 6: GitHub Actions — build e push das imagens para o ghcr

Buildar as duas imagens nos runners e publicá-las privadas no ghcr, encadeado após o CI verde na `main`.

**Files:**
- Create: `.github/workflows/deploy.yml` (job de build/push; o deploy por SSH entra na Task 9)

**Interfaces:**
- Consumes: workflow `CI` (nome exato `CI`, definido em `.github/workflows/ci.yml`).
- Produces: imagens `ghcr.io/arthurmoreiras/causor-backend:<sha>` e `causor-frontend:<sha>` (+ `latest`).

- [ ] **Step 1 (👤): Variáveis/segredos do frontend no GitHub**

Repo GitHub → **Settings → Secrets and variables → Actions**:
- Variável (Variables) `NEXT_PUBLIC_SUPABASE_URL` = `https://ufzrhthkfmlzhaykkfsl.supabase.co`
- Segredo (Secrets) `NEXT_PUBLIC_SUPABASE_ANON_KEY` = anon/public key (Supabase → Project Settings → API).

(A `NEXT_PUBLIC_API_BASE` é fixa `https://api.causorai.com` e vai direta no workflow.)

- [ ] **Step 2: Criar `.github/workflows/deploy.yml` (só build/push nesta task)**

```yaml
name: Deploy

on:
  workflow_run:
    workflows: ["CI"]
    types: [completed]
    branches: [main]

jobs:
  build-push:
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.workflow_run.head_sha }}

      - name: Log in to ghcr
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build & push backend
        uses: docker/build-push-action@v6
        with:
          context: ./backend
          push: true
          tags: |
            ghcr.io/arthurmoreiras/causor-backend:${{ github.event.workflow_run.head_sha }}
            ghcr.io/arthurmoreiras/causor-backend:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build & push frontend
        uses: docker/build-push-action@v6
        with:
          context: ./frontend
          push: true
          build-args: |
            NEXT_PUBLIC_API_BASE=https://api.causorai.com
            NEXT_PUBLIC_SUPABASE_URL=${{ vars.NEXT_PUBLIC_SUPABASE_URL }}
            NEXT_PUBLIC_SUPABASE_ANON_KEY=${{ secrets.NEXT_PUBLIC_SUPABASE_ANON_KEY }}
          tags: |
            ghcr.io/arthurmoreiras/causor-frontend:${{ github.event.workflow_run.head_sha }}
            ghcr.io/arthurmoreiras/causor-frontend:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

- [ ] **Step 3: Commit e push numa branch de teste**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: build e push das imagens do Causor para o ghcr"
git push origin HEAD
```

- [ ] **Step 4 (👤/🤖): Merge na `main` e verificar as imagens**

Após o merge na `main`, o `CI` roda; ao passar, o `Deploy → build-push` dispara. Verificar em **GitHub → repo → Packages** que apareceram `causor-backend` e `causor-frontend` com a tag do SHA. (Se `build-push` não disparar, conferir que o `name:` do CI é exatamente `CI`.)

**Deliverable:** imagens privadas publicadas no ghcr a cada push verde na `main`.

---

## Task 7: DNS + provisionar a VPS (.env, login ghcr, arquivos)

Apontar os subdomínios e deixar a VPS pronta para baixar as imagens.

**Files:** (nenhum no repo — configuração externa e no servidor)

- [ ] **Step 1 (👤): Criar os registros A no DNS de `causorai.com`**

No registrador/DNS do `causorai.com`, criar:
- `A  app  → 179.197.70.156`
- `A  api  → 179.197.70.156`
(TTL baixo, ex.: 300s, durante o setup.)

- [ ] **Step 2 (🤖): Verificar propagação do DNS**

```bash
nslookup app.causorai.com 1.1.1.1
nslookup api.causorai.com 1.1.1.1
```
Expected: ambos resolvem para `179.197.70.156`. (Pode levar alguns minutos.)

- [ ] **Step 3 (🤖): Copiar os arquivos de infra para a VPS**

Sem Caddyfile aqui — o TLS/proxy é o do stack `infolex-evo` (integração na Task 8).
```bash
ssh -i "$HOME/.ssh/causor_deploy" deploy@179.197.70.156 'sudo mkdir -p /opt/causor && sudo chown deploy:deploy /opt/causor'
scp -i "$HOME/.ssh/causor_deploy" infra/docker-compose.prod.yml deploy@179.197.70.156:/opt/causor/docker-compose.yml
scp -i "$HOME/.ssh/causor_deploy" infra/.env.prod.example deploy@179.197.70.156:/opt/causor/.env.example
```
Expected: transferências concluídas.

- [ ] **Step 4 (🤖 + 👤): Criar o `/opt/causor/.env` com os segredos reais**

Reutilizar os valores que já funcionam no `backend/.env` local (mesmo Supabase, mesma `ANTHROPIC_API_KEY`, mesmo `CAUSOR_DATAJUD_API_KEY`, `CAUSOR_SUPABASE_JWT_SECRET`). Arthur confirma/fornece cada valor; Claude escreve o arquivo na VPS via SSH (sem imprimir os segredos no chat). Ajustar para produção: `CAUSOR_CORS_ORIGINS=https://app.causorai.com`, `CAUSOR_FILING_MODE=sandbox`, `CAUSOR_OBJECT_STORE_LOCAL_PATH=/app/artifacts/objects`.
Expected: `ssh ... 'test -f /opt/causor/.env && echo ok'` → `ok`.

- [ ] **Step 5 (👤): Criar um PAT de leitura do ghcr**

GitHub → **Settings → Developer settings → Personal access tokens** → token (classic) com escopo **`read:packages`**. Guardar o valor para o Step 6.

- [ ] **Step 6 (🤖): `docker login` no ghcr a partir da VPS**

```bash
ssh -i "$HOME/.ssh/causor_deploy" deploy@179.197.70.156 \
  'echo "<PAT_read_packages>" | docker login ghcr.io -u ArthurMoreiraS --password-stdin'
```
Expected: `Login Succeeded`. (Credenciais ficam em `~/.docker/config.json` do `deploy`; o deploy do Actions reusa.)

**Deliverable:** DNS apontando, arquivos de infra + `.env` na VPS, e a VPS autenticada para baixar imagens privadas.

---

## Task 8: Subir o Causor, plugar no Caddy compartilhado, crons e validação ponta a ponta

Subir os containers do Causor, integrar ao Caddy existente do `infolex-evo` (com backup + reload, sem downtime pros outros clientes) e confirmar HTTPS + login.

**Files:**
- Create (na VPS): `/etc/cron.d/causor`
- Modify (na VPS): `/opt/infolex-evo/Caddyfile` (backup antes)

- [ ] **Step 1 (🤖): Baixar as imagens e migrar o banco**

```bash
ssh -i "$HOME/.ssh/causor_deploy" deploy@179.197.70.156 '
cd /opt/causor && docker compose pull &&
docker compose run --rm migrate'
```
Expected: `pull` baixa backend/frontend; o `migrate` roda `alembic upgrade head` contra o Supabase e sai com código 0 (pode ser "no-op" se já estiver no head).

- [ ] **Step 2 (🤖): Subir os serviços do Causor**

```bash
ssh -i "$HOME/.ssh/causor_deploy" deploy@179.197.70.156 'cd /opt/causor && docker compose up -d && docker compose ps'
```
Expected: `causor-backend`, `causor-worker`, `causor-frontend` como `running`/`healthy`. Nenhuma porta publicada no host (ver `docker compose ps` — sem `0.0.0.0:...` nas linhas do Causor).

- [ ] **Step 3 (🤖): Confirmar que os containers do Causor estão na rede `edge`**

```bash
ssh -i "$HOME/.ssh/causor_deploy" deploy@179.197.70.156 \
  'docker network inspect edge --format "{{range .Containers}}{{.Name}} {{end}}"'
```
Expected: a lista inclui `causor-backend`, `causor-frontend` e `infolex-evo-caddy-1`.

- [ ] **Step 4 (🤖): Backup do Caddyfile compartilhado e adicionar as entradas do Causor**

```bash
ssh -i "$HOME/.ssh/causor_deploy" deploy@179.197.70.156 '
sudo cp /opt/infolex-evo/Caddyfile /opt/infolex-evo/Caddyfile.bak.$(date +%Y%m%d%H%M%S) &&
sudo tee -a /opt/infolex-evo/Caddyfile > /dev/null <<'"'"'EOF'"'"'

app.causorai.com {
	reverse_proxy causor-frontend:3000
}

api.causorai.com {
	reverse_proxy causor-backend:8000
}
EOF
cat /opt/infolex-evo/Caddyfile'
```
Expected: o arquivo impresso no fim mostra as 4 entradas (`evo.infolex.adv.br`, `evo.operlyapp.com`, `app.causorai.com`, `api.causorai.com`) e existe um novo `Caddyfile.bak.<timestamp>`.

- [ ] **Step 5 (🤖): Recarregar o Caddy existente sem downtime**

```bash
ssh -i "$HOME/.ssh/causor_deploy" deploy@179.197.70.156 \
  'docker exec infolex-evo-caddy-1 caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile'
```
Expected: sem erro (`caddy reload` não reinicia o container nem derruba conexões existentes).

- [ ] **Step 6 (🤖): Confirmar que os sites existentes continuam de pé**

```bash
curl -fsS -o /dev/null -w "evo.infolex.adv.br -> %{http_code}\n" https://evo.infolex.adv.br
curl -fsS -o /dev/null -w "evo.operlyapp.com -> %{http_code}\n" https://evo.operlyapp.com
```
Expected: ambos continuam respondendo (qualquer código HTTP normal do Evolution API, não erro de conexão) — prova de que o reload não quebrou o que já estava em produção. Se algo falhar, restaurar com `sudo cp Caddyfile.bak.<timestamp> Caddyfile && docker exec infolex-evo-caddy-1 caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile`.

- [ ] **Step 7 (🤖): Verificar TLS e health do Causor**

```bash
sleep 15   # dar tempo ao Caddy de emitir os certificados para os novos dominios
curl -fsS https://api.causorai.com/health
curl -fsS -o /dev/null -w "%{http_code}\n" https://app.causorai.com/login
```
Expected: `{"status":"ok"}` e `200`, ambos com certificado válido (sem `-k`). Se o certificado falhar, conferir que o DNS resolve (Task 7 Step 2) e checar `docker logs infolex-evo-caddy-1 --tail 50`.

- [ ] **Step 8 (👤): Autorizar o domínio no Supabase Auth**

Supabase → **Authentication → URL Configuration**: definir *Site URL* `https://app.causorai.com` e adicionar em *Redirect URLs*. (Sem isso o login redireciona errado.)

- [ ] **Step 9 (🤖 + 👤): Teste de login real**

Arthur abre `https://app.causorai.com/login` e entra com a conta de piloto. Confirmar que a inbox carrega (o frontend fala com `https://api.causorai.com` sem erro de CORS). Se der CORS, revisar `CAUSOR_CORS_ORIGINS` no `.env` e `docker compose up -d` de novo.

- [ ] **Step 10 (🤖): Agendar os crons no host**

Criar `/etc/cron.d/causor` na VPS:
```cron
# capture-due: de hora em hora | process-autos-due: a cada 5 min
0  *    * * * deploy cd /opt/causor && /usr/bin/docker compose run --rm backend python -m app.cli capture-due >> /var/log/causor-cron.log 2>&1
*/5 *   * * * deploy cd /opt/causor && /usr/bin/docker compose run --rm backend python -m app.cli process-autos-due >> /var/log/causor-cron.log 2>&1
```
Aplicar:
```bash
ssh -i "$HOME/.ssh/causor_deploy" deploy@179.197.70.156 '
sudo tee /etc/cron.d/causor > /dev/null <<'"'"'EOF'"'"'
0  *    * * * deploy cd /opt/causor && /usr/bin/docker compose run --rm backend python -m app.cli capture-due >> /var/log/causor-cron.log 2>&1
*/5 *   * * * deploy cd /opt/causor && /usr/bin/docker compose run --rm backend python -m app.cli process-autos-due >> /var/log/causor-cron.log 2>&1
EOF
sudo chmod 0644 /etc/cron.d/causor && sudo systemctl restart cron && echo cron-ok'
```
Expected: `cron-ok`.

- [ ] **Step 11 (🤖): Verificar uma execução manual do cron de captura**

```bash
ssh -i "$HOME/.ssh/causor_deploy" deploy@179.197.70.156 \
  'cd /opt/causor && docker compose run --rm backend python -m app.cli capture-due'
```
Expected: roda sem exceção e sai com código 0 (mesmo que não haja OAB "vencida" a capturar).

**Deliverable:** Causor no ar em `https://app.causorai.com` com login funcionando e crons agendados.

---

## Task 9: GitHub Actions — deploy automático por SSH

Ligar o gatilho: após build/push, o Actions atualiza a VPS sozinho.

**Files:**
- Modify: `.github/workflows/deploy.yml` (adicionar o job `deploy`)

**Interfaces:**
- Consumes: imagens do job `build-push` (Task 6); segredos SSH do repo.

- [ ] **Step 1 (👤): Segredos de deploy no GitHub**

Repo → Settings → Secrets and variables → Actions → **Secrets**:
- `VPS_HOST` = `179.197.70.156`
- `VPS_USER` = `deploy`
- `VPS_SSH_KEY` = conteúdo de `~/.ssh/causor_deploy` (a chave **privada**).

- [ ] **Step 2: Adicionar o job `deploy` em `.github/workflows/deploy.yml`**

Acrescentar ao final do arquivo (depois de `build-push`):
```yaml
  deploy:
    needs: build-push
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/causor
            export IMAGE_TAG=${{ github.event.workflow_run.head_sha }}
            echo "IMAGE_TAG=$IMAGE_TAG" > .image_tag.env
            docker compose --env-file .env --env-file .image_tag.env pull
            docker compose --env-file .env --env-file .image_tag.env run --rm migrate
            docker compose --env-file .env --env-file .image_tag.env up -d
            sleep 15
            curl -fsS https://api.causorai.com/health
```

- [ ] **Step 3: Commit e push da alteração**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: deploy automatico por SSH apos build (push na main)"
git push origin HEAD
```

- [ ] **Step 4 (👤/🤖): Merge na main e acompanhar o deploy**

Após o merge, acompanhar em **GitHub → Actions → Deploy**: `build-push` → `deploy` devem ficar verdes e o `curl` de health passar no fim.

**Deliverable:** pipeline completo — push na `main` (CI verde) atualiza a VPS sem intervenção.

---

## Task 10: Validação ponta a ponta e runbook operacional

Provar o ciclo automático de verdade e documentar a operação.

**Files:**
- Modify: `DEPLOY-VPS.md` (adicionar seção "Operação / runbook")

- [ ] **Step 1: Mudança trivial e visível**

Alterar o payload do `/health` do backend para incluir a versão (ex.: `{"status":"ok","version":"deploy-test-1"}`) num branch, ou ajustar um texto no frontend. Commit.

```bash
git commit -am "chore: marca de teste do auto-deploy"
git push origin HEAD
```

- [ ] **Step 2 (👤): Merge na main e observar o deploy automático**

Após merge: CI verde → Deploy roda → em ~2-4 min a mudança aparece. Verificar:
```bash
curl -fsS https://api.causorai.com/health
```
Expected: reflete a mudança do Step 1.

- [ ] **Step 3: Reverter a marca de teste**

```bash
git revert --no-edit <sha-do-step-1>
git push origin HEAD   # (via PR/merge) — confirma que o revert tambem deploya
```

- [ ] **Step 4: Documentar o runbook em `DEPLOY-VPS.md`**

Adicionar seção com: onde vive o `.env` (`/opt/causor/.env`), como ver logs (`docker compose logs -f <serviço>`), como fazer rollback (`export IMAGE_TAG=<sha-anterior>; docker compose up -d`), onde ficam os crons (`/etc/cron.d/causor`, log em `/var/log/causor-cron.log`), e como o TLS/proxy funciona: o Causor **não tem Caddy próprio** — depende do `infolex-evo-caddy-1` e do arquivo `/opt/infolex-evo/Caddyfile` (compartilhado com outro cliente); qualquer alteração nesse Caddyfile exige backup + `caddy reload` (nunca restart) e checar `evo.infolex.adv.br`/`evo.operlyapp.com` depois.

- [ ] **Step 5: Commit**

```bash
git add DEPLOY-VPS.md
git commit -m "docs: runbook operacional do deploy na VPS"
```

**Deliverable:** auto-deploy comprovado ponta a ponta e runbook documentado.

---

## Self-review (cobertura do spec, revisado após inventário de 2026-07-28)

- **Docker Compose, sem Caddy próprio** → Tasks 3–5, 8 (reusa o Caddy do `infolex-evo` via rede `edge`). ✅
- **HTTPS automático + domínio** → Task 8 Steps 4-7 (entradas no Caddyfile compartilhado + reload + verificação TLS), Task 7 (DNS). ✅
- **Supabase remoto, sem Postgres/Redis** → não há serviço de banco no Compose (Task 5). ✅
- **Segredos só na VPS** → Task 7 Step 4 (.env na VPS); imagens sem segredo. ✅
- **Imagens privadas no ghcr + deploy direto com CI verde** → Tasks 6, 9 (`workflow_run` gated em `conclusion == success`). ✅
- **Cron capture-due / process-autos-due** → Task 8 Step 10. ✅
- **Worker sempre on** → Task 5 (serviço `worker`). ✅
- **Hardening (chave SSH, firewall)** → Task 2 (Docker já instalado, ajustado). ✅
- **Não quebrar o que já roda** → Task 1 (snapshot + inventário, concluído); Task 8 Steps 4-6 (backup do Caddyfile compartilhado + reload sem downtime + verificação explícita de que `evo.infolex.adv.br`/`evo.operlyapp.com` continuam de pé). ✅
- **Tesseract / sem browsers Playwright** → Task 3. ✅
- **Migrations no deploy** → Task 8 Step 1, Task 9 Step 2. ✅
- **Coexistência com stacks de terceiro na mesma VPS** (achado novo, fora do spec original) → Task 8 Steps 3-6 cobrem a integração segura; documentado em `DEPLOY-VPS.md` §2.1 e §7. ✅
