# Deploy do Causor na VPS (design)

Design do hospedagem do Causor (backend FastAPI + frontend Next.js) numa VPS,
com **deploy automático a cada push na `main`**. Este documento é o **desenho
acordado**; o passo a passo de execução vira um plano de implementação à parte.

> Status: **em execução.** Inventário da VPS feito em 2026-07-28.
> Data do design: 2026-07-27. Revisado em 2026-07-28 após inventário real da VPS.
> Domínio: **causorai.com** (`app.causorai.com` = frontend, `api.causorai.com` = backend).

---

## 1. Contexto e decisões travadas

- **Objetivo:** publicar backend + frontend com HTTPS e deploy contínuo, como
  passo 1 da "trilha do piloto" do [`docs/estado.md`](docs/estado.md).
- **Banco:** continua sendo o **Supabase remoto** (Postgres + Auth). A VPS
  **não** hospeda Postgres nem Redis (o worker de jobs é DB-based, não usa
  Celery/Redis).
- **Agente local:** continua rodando na máquina do advogado — **nunca** na VPS.

| Decisão | Escolha |
|---|---|
| Orquestração | **Docker Compose** (isola o Causor do que já roda na VPS) |
| Proxy + TLS | **Caddy existente** do stack `infolex-evo` (rede `edge` compartilhada) — ver §2.1 |
| CI/CD | **GitHub Actions**: build nos runners → **ghcr.io privado** → deploy por SSH |
| Registry | Imagens **privadas** no ghcr; VPS baixa com token de leitura |
| Gatilho de deploy | **Push na `main` + CI verde → deploy direto** (sem aprovação manual) |

### VPS alvo (Hostinger)
- Plano **KVM 1**: 1 vCPU, **4 GB RAM** (~1.4 GB livres hoje), 50 GB disco
  (~42 GB livres), 4 TB banda.
- **Ubuntu 24.04 LTS**, Brasil – Campinas.
- IP: **179.197.70.156**.
- **Docker já instalado.** Inventário (2026-07-28) encontrou dois stacks
  Docker existentes — ver §2.1.

---

## 2. Topologia

### 2.1 Achado do inventário (2026-07-28): portas 80/443 já ocupadas

A VPS já roda dois stacks Docker do Arthur (gateways de WhatsApp via
Evolution API): **`infolex-evo`** (cliente Infolex, escritório de advocacia)
e **`operly-evo`** (Operly). O `infolex-evo` inclui um **Caddy que já ocupa
as portas 80/443** do host e roteia por domínio usando uma **rede Docker
externa chamada `edge`** — padrão já em uso para hospedar múltiplos produtos
atrás de um único Caddy (prova: o Caddyfile existente já roteia
`evo.operlyapp.com` para o stack `operly-evo`, um produto diferente).

**Decisão:** o Causor **não sobe seu próprio Caddy**. Backend e frontend
entram na rede `edge` existente; duas entradas novas são adicionadas ao
`Caddyfile` compartilhado (`/opt/infolex-evo/Caddyfile`, com backup antes) e
o Caddy existente recebe um `reload` (sem downtime, não afeta
`evo.infolex.adv.br` nem `evo.operlyapp.com` — produção de terceiro).

### 2.2 Diagrama

```
Internet ─► Caddy existente (infolex-evo-caddy-1, rede "edge", 80/443, HTTPS automático)
              ├─ app.causorai.com   ─► causor-frontend (Next.js, :3000, via rede edge)
              ├─ api.causorai.com   ─► causor-backend  (uvicorn,  :8000, via rede edge)
              ├─ evo.infolex.adv.br ─► infolex-evo-evolution-api-1   [stack existente, não muda]
              └─ evo.operlyapp.com  ─► operly-evolution-api           [stack existente, não muda]

causor-backend / causor-worker / cron ──► Supabase (Postgres + Auth) na nuvem   [não muda]
                                     └──► DataJud / DJEN / Anthropic (APIs externas)
```

Dois subdomínios (`app.` para o frontend, `api.` para o backend) em vez de
path-prefix: mais limpo, e o CORS já é resolvido por Bearer token. Os
containers do Causor **não publicam porta no host** — só existem na rede
interna do Causor + na rede `edge` compartilhada.

---

## 3. Serviços / processos

| Serviço | Comando | Tipo |
|---|---|---|
| `backend` | `uvicorn app.api.main:app --host 0.0.0.0 --port 8000` | sempre on |
| `worker` | `python -m app.cli worker` | sempre on |
| `frontend` | `next start` | sempre on |
| `migrate` | `alembic upgrade head` | roda 1x no deploy e sai |
| cron captura | `python -m app.cli capture-due` | agendado (partida: de hora em hora) |
| cron autos | `python -m app.cli process-autos-due` | agendado (partida: a cada 5 min) |

O cron será **cron do host** chamando `docker compose run --rm <serviço>`
(mais simples e auditável que um container-cron dedicado). As frequências são
ponto de partida e podem ser ajustadas depois de observar carga real.

---

## 4. HTTPS e domínio

1. Criar **2 registros A** no DNS do domínio: `app` e `api` → **179.197.70.156**.
2. O **Caddy existente** (`infolex-evo-caddy-1`) emite e renova os
   certificados sozinho (Let's Encrypt) para os novos domínios assim que as
   entradas forem adicionadas ao Caddyfile — sem config manual de TLS.
3. No painel do **Supabase**: adicionar `https://app.causorai.com` em *Site URL*
   e *Redirect URLs* (senão o login quebra).
4. No backend: `CAUSOR_CORS_ORIGINS=https://app.causorai.com`.

---

## 5. Segredos e configuração

- **Segredos do backend** — `.env` **só na VPS** (nunca no git, nunca na imagem),
  injetados em runtime via `env_file`:
  - `CAUSOR_DATABASE_URL` (Supabase Postgres)
  - `CAUSOR_DATAJUD_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `CAUSOR_SUPABASE_JWT_SECRET`
  - `CAUSOR_CORS_ORIGINS=https://app.causorai.com`
- **Config do frontend** — variáveis `NEXT_PUBLIC_*` são públicas por natureza e
  entram como **build args** no CI (ficam embutidas na imagem):
  - `NEXT_PUBLIC_API_BASE=https://api.causorai.com`
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- **Secrets no GitHub Actions:** chave SSH de deploy, host/usuário da VPS, e os
  valores `NEXT_PUBLIC_*`. O **token de leitura do ghcr** fica na VPS
  (via `docker login ghcr.io`), não no repositório.

---

## 6. Pipeline CI/CD (push na `main`)

```
git push main
  └─► GitHub Actions
        1. CI atual (gate): ruff + pytest + vitest + build check
        2. build imagens backend + frontend  →  push ghcr.io (privado)
        3. ssh VPS:
             docker login ghcr.io
             docker compose pull
             docker compose run --rm migrate      # alembic upgrade head
             docker compose up -d                 # backend/worker/frontend na rede edge
             smoke test: GET https://api.causorai.com/health
```

Nada nesse pipeline reinicia o Caddy existente — as entradas do Caddyfile
compartilhado são adicionadas **uma vez**, manualmente, na primeira subida
(§7); deploys seguintes só atualizam os containers do Causor.

- **Build sempre nos runners da GitHub**, nunca na VPS (protege o 1 vCPU / 4 GB;
  o `next build` é o passo pesado).
- **Rollback:** redeploy da tag anterior da imagem.
- O gatilho automático **só é ligado depois** da primeira subida manual estar
  estável e validada.

---

## 7. Rede, firewall e hardening

A caixa veio crua (root por senha, sem firewall configurado). Como parte do
setup:

- Criar **usuário sudo não-root** (`deploy`) para as operações de deploy.
- **SSH só por chave**; desabilitar login de root e por senha.
- **ufw** + **firewall da Hostinger**: liberar apenas **22, 80, 443** (80/443
  já são usados pelo Caddy existente — não mudam com o Causor).
- (Opcional) **fail2ban**.
- Containers do Causor **não expõem porta** no host — só entram na rede
  `edge`, que o Caddy existente já enxerga.

### Integração com o Caddy compartilhado

1. Backup do Caddyfile atual: `cp Caddyfile Caddyfile.bak.$(date +%s)`.
2. Adicionar os dois blocos novos (`app.causorai.com`, `api.causorai.com`) ao
   `/opt/infolex-evo/Caddyfile`.
3. `docker exec infolex-evo-caddy-1 caddy reload --config /etc/caddy/Caddyfile`
   — recarrega sem downtime, não afeta `evo.infolex.adv.br` nem
   `evo.operlyapp.com`.
4. Os containers `causor-backend`/`causor-frontend` precisam de um **alias de
   rede** nesses nomes na rede `edge` (via `docker-compose.prod.yml`) para o
   Caddyfile conseguir resolvê-los.

---

## 8. "Não quebrar o que já roda" — resultado do inventário (2026-07-28)

Feito antes de qualquer alteração na VPS:

1. ✅ **Snapshot da VPS** tirado no painel Hostinger.
2. ✅ SSH por chave + **inventário**: Docker já instalado; dois stacks
   existentes (`infolex-evo`, `operly-evo`) usando ~1 GB de RAM; portas 80/443
   ocupadas pelo Caddy do `infolex-evo`; 42 GB de disco livres.
3. ✅ **Proxy existente identificado** → decisão tomada com o Arthur: integrar
   via rede `edge` compartilhada em vez de subir um segundo proxy (§2.1, §7).

---

## 9. Fora de escopo agora (YAGNI)

- Redis / Celery (worker é DB-based).
- Postgres self-hosted (o banco é o Supabase remoto).
- Coolify / painel PaaS (pesado demais para 4 GB com carga existente).
- Ambiente de staging separado, escala horizontal.
- Observability pesada. Monitoramento externo do backend/cron e alertas de
  prazo já estão no `estado.md` como **passos seguintes**, após o deploy de pé.

---

## 10. Pendências a preencher antes de executar

- [x] **Domínio definido:** `causorai.com`. Falta criar os registros A
      (`app.causorai.com`, `api.causorai.com` → 179.197.70.156).
- [ ] Confirmar valores `NEXT_PUBLIC_SUPABASE_URL` / `ANON_KEY` (do
      `frontend/.env.local` atual).
- [x] Inventário real da VPS feito (2026-07-28) — proxy existente encontrado,
      integração via rede `edge` decidida (§2.1, §7).
- [ ] Ajuste fino das frequências de cron após observar carga.
