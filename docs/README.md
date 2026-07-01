# Documentação do Causor

Índice único da documentação viva. Arquivos históricos ficam em
[`historico/`](historico/) e não refletem o estado atual.

## Estado e direção

| Arquivo | O que tem | Quando ler |
|---|---|---|
| [`estado.md`](estado.md) | Status atual e próximos passos do MVP | Antes de qualquer decisão de produto/arquitetura |
| [`produto/PRD.md`](produto/PRD.md) | PRD estratégico, visão, mercado, features, roadmap | Para contexto de direção, não de implementação corrente |

## Operação

| Arquivo | O que tem | Quando ler |
|---|---|---|
| [`../../RODAR-LOCAL.md`](../../RODAR-LOCAL.md) | Quickstart para subir backend + frontend | Toda vez que for rodar localmente pela primeira vez no dia |
| [`operacao/local-dev.md`](operacao/local-dev.md) | Setup completo, troubleshooting e captura agendada local | Primeira instalação ou quando algo quebrar |
| [`operacao/deploy.md`](operacao/deploy.md) | Runbook de produção (envs, cron, provisionamento) | Ao publicar ou configurar ambiente definitivo |
| [`operacao/onboarding-piloto.md`](operacao/onboarding-piloto.md) | Fluxo de cadastrar o primeiro escritório/advogado | Ao onboardar um piloto |

## Áreas funcionais

| Arquivo | O que tem | Quando ler |
|---|---|---|
| [`areas/pje-assistido.md`](areas/pje-assistido.md) | Protocolo PJe assistido, vault, assinatura, como testar | Antes de mexer no conector PJe ou no fluxo de assinatura |

## Agentes

| Arquivo | O que tem | Quando ler |
|---|---|---|
| [`../../AGENTS.md`](../../AGENTS.md) | Regras para agentes de IA (opencode, Claude Code) | Leitura obrigatória de todo agente antes de trabalhar no repo |
| [`../../CLAUDE.md`](../../CLAUDE.md) | Ponteiro para `AGENTS.md` | Compatibilidade com Claude Code |

## Histórico (não usar para inferir estado atual)

| Arquivo | O que tem | Quando ler |
|---|---|---|
| [`historico/README.md`](historico/README.md) | Aviso sobre a pasta histórica | Antes de abrir qualquer arquivo em `historico/` |
| [`historico/superpowers/`](historico/superpowers/) | Planos e specs antigos por data | Apenas para entender por que algo foi feito no passado |
