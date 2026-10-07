# Deploy em produção

O Causor roda numa VPS (Hostinger, Ubuntu 24.04, 1 vCPU / 4 GB) com Docker
Compose. Banco e Auth ficam num projeto Supabase gerenciado (plano Free). A VPS
não hospeda Postgres nem Redis; as filas são tabelas no banco.

- Frontend: `https://app.causorai.com`
- API: `https://api.causorai.com` (`/health` → `{"status":"ok"}`)

## Serviços

Definidos em [`infra/docker-compose.prod.yml`](../../infra/docker-compose.prod.yml),
todos com a mesma imagem do backend, exceto o frontend:

| Serviço | Comando | Função |
|---|---|---|
| `backend` | `uvicorn app.api.main:app` | API (rede `edge`, atrás do Caddy). |
| `worker` | `python -m app.cli worker` | Jobs de captura OAB, análise de prazo e trabalhos. |
| `autos-worker` | `python -m app.autos.worker` | Extração, OCR e resumo dos documentos. |
| `capture-scheduler` | `python -m app.capture.service` | Enfileira capturas devidas ([operação](captura-periodica.md)). |
| `frontend` | `next start` | Interface (rede `edge`). |
| `migrate` | `alembic upgrade head` | Roda uma vez por deploy (perfil `tools`). |

`backend`, `worker` e `autos-worker` compartilham o volume `causor_artifacts`,
onde ficam os PDFs enviados.

## Pipeline

Push na `main` → workflow **CI** (backend, frontend, PostgreSQL 16/17) → se
verde, workflow **Deploy**:

1. Constrói as imagens nos runners do GitHub e publica no `ghcr.io` (privado).
   O build nunca roda na VPS.
2. Conecta por SSH (secrets `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`) e executa
   [`infra/deploy.sh`](../../infra/deploy.sh) na versão do commit.
3. O script baixa o Compose da mesma versão, faz `pull`, confere a configuração
   de modelos, roda `migrate`, sobe os serviços com `--wait`, **verifica o SHA da
   imagem em cada um dos cinco serviços** e chama `/health`. API antiga saudável
   não conta como deploy concluído.

O workflow também aceita disparo manual (`workflow_dispatch`), desde que o mesmo
SHA tenha CI verde. Commits com `[skip ci]` (atualizações de documentação) não
implantam.

## Onde estão as coisas na VPS

| O quê | Onde |
|---|---|
| Compose e segredos | `/opt/causor/docker-compose.yml`, `/opt/causor/.env` (permissão 600, nunca no git) |
| Versão implantada | `/opt/causor/.image_tag.env` (a anterior em `.image_tag.previous.env`) |
| Modelo de `.env` | [`infra/.env.prod.example`](../../infra/.env.prod.example) |
| Caddy (TLS e proxy) | Container `infolex-evo-caddy-1`, arquivo `/opt/infolex-evo/Caddyfile`, rede Docker `edge` |

Variáveis `NEXT_PUBLIC_*` do frontend são públicas e entram como build args no
CI. A chave `service_role` e segredos do backend ficam só no `.env` da VPS.

## Operação

Logs:

```bash
cd /opt/causor
docker compose --env-file .env --env-file .image_tag.env logs -f --tail 100 backend
# troque por worker, autos-worker, capture-scheduler ou frontend
```

Rollback para uma versão anterior com CI verde:

```bash
cd /opt/causor
echo "IMAGE_TAG=<sha-anterior>" > .image_tag.env
docker compose --env-file .env --env-file .image_tag.env pull
docker compose --env-file .env --env-file .image_tag.env up -d
```

Migrações não são revertidas automaticamente; confira antes de voltar uma
versão que tenha migração nova.

## Caddy compartilhado

O Causor não tem proxy próprio. O Caddy da VPS também serve outros produtos do
fundador. Para qualquer mudança no `Caddyfile`:

1. Backup: `sudo cp Caddyfile Caddyfile.bak.$(date +%Y%m%d%H%M%S)`.
2. Editar.
3. `docker exec infolex-evo-caddy-1 caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile`
   — **nunca** `docker restart` nesse container.
4. Conferir com `curl` todos os domínios servidos, não só os do Causor.

## Lições já aprendidas

- Pull de imagem privada exige PAT **clássico** com `repo` + `read:packages`;
  PAT fine-grained não funciona com o Container Registry.
- A imagem do frontend precisa de Node 22 (pnpm 11), e o estágio de
  dependências precisa copiar `pnpm-workspace.yaml`.
- No Ubuntu da Hostinger, `/etc/ssh/sshd_config.d/50-cloud-init.conf` reativa
  login por senha; confira com `sudo sshd -T | grep password` após mexer no SSH.
- Ruff está limitado a `<0.16` no `pyproject.toml`; versões novas quebraram o CI.

## Primeiro acesso de um escritório

Ver [onboarding do piloto](onboarding-piloto.md).
