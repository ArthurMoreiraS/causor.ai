# Inventário da VPS antes do deploy do Causor

Data: 2026-07-28. VPS Hostinger `srv1825391.hstgr.cloud` (179.197.70.156),
Ubuntu 24.04 LTS, KVM 1 (1 vCPU / 4 GB RAM / 50 GB disco). Levantamento
**somente leitura**, feito antes de qualquer alteração, via SSH por chave
(`~/.ssh/causor_deploy`).

## Recursos

- **RAM:** 3915 MB total; ~1008 MB em uso pelos stacks existentes; ~1446 MB
  livres, ~2907 MB "available" (com buff/cache).
- **Disco:** 48 GB em `/dev/sda1`; 6.4 GB usados, 42 GB livres (14%).
- **Serviços systemd em execução:** apenas os de base do Ubuntu (ssh, cron,
  docker, containerd, unattended-upgrades, etc.) — nada de Nginx/Apache fora
  do Docker.

## Stacks Docker já rodando

Docker Engine + Compose plugin **já instalados**. Dois stacks independentes,
ambos gateways de WhatsApp via Evolution API, cada um com Postgres e Redis
próprios:

### `infolex-evo` (`/opt/infolex-evo/`) — cliente Infolex (escritório de advocacia)
- `infolex-evo-caddy-1` (caddy:2-alpine) — **publica 80/443 no host**,
  roteia por domínio via Caddyfile.
- `infolex-evo-evolution-api-1` — expõe só `8080/tcp` interno.
- `infolex-evo-postgres-1`, `infolex-evo-redis-1` — só rede interna.
- Caddyfile atual:
  ```
  evo.infolex.adv.br {
      reverse_proxy infolex-evo-evolution-api-1:8080
  }
  evo.operlyapp.com {
      reverse_proxy operly-evolution-api:8080
  }
  ```
- Roda numa **rede Docker externa chamada `edge`**, compartilhada com o
  stack `operly-evo` (prova: a entrada `evo.operlyapp.com` acima aponta para
  um container de outro stack).

### `operly-evo` (`/opt/operly-evolution/`) — Operly
- `operly-evo-evolution-api-1`, `operly-evo-postgres-1`, `operly-evo-redis-1`
  — nenhuma porta publicada no host; alcançado publicamente só através do
  Caddy do `infolex-evo` via rede `edge`.

## Portas ouvindo no host

| Porta | Processo |
|---|---|
| 22 | sshd |
| 80, 443 | docker-proxy (Caddy do `infolex-evo`) |
| 127.0.0.53/54:53 | systemd-resolved (local) |

**Nenhuma porta livre em 80/443** — qualquer proxy novo precisa reusar o
Caddy existente, não pode publicar essas portas de novo.

## Decisão tomada (alinhada com o Arthur)

O Causor **não sobe Caddy próprio**. Em vez disso:
1. `causor-backend` e `causor-frontend` entram na rede externa `edge` (além
   da rede interna própria do Causor).
2. O `Caddyfile` de `infolex-evo` ganha duas entradas novas
   (`app.causorai.com`, `api.causorai.com`), com backup do arquivo antes da
   edição.
3. `docker exec infolex-evo-caddy-1 caddy reload` aplica a mudança sem
   downtime — não afeta `evo.infolex.adv.br` nem `evo.operlyapp.com`
   (produção de terceiro).

Detalhado em [`DEPLOY-VPS.md`](../../../DEPLOY-VPS.md) §2.1 e §7, e nas Tasks
5/8 de [`2026-07-27-deploy-vps.md`](../plans/2026-07-27-deploy-vps.md).

## Sem conflitos identificados

- Sem crontab de root, sem `/etc/cron.d` de terceiros relevante (só
  `e2scrub_all`/`sysstat`, padrão do Ubuntu).
- `/opt` e `/home` sem outros diretórios além dos dois stacks acima.
- Nomes de container (`causor-backend`, `causor-worker`, `causor-frontend`)
  não colidem com os existentes.
