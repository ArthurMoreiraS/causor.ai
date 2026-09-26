# Documentação do Causor

Índice único da documentação viva. Arquivos históricos ficam em
[`historico/`](historico/) e não refletem o estado atual.

## Estado e direção

| Arquivo | O que tem | Quando ler |
|---|---|---|
| [`produto/direcao-pos-reuniao-2026-09-25.md`](produto/direcao-pos-reuniao-2026-09-25.md) | Direção após a reunião: captura, prazo, contexto, minuta e revisão; UI anterior restaurada | Antes de decidir prioridade de produto ou interface |
| [`produto/marco-caso-real-2026-09-25.md`](produto/marco-caso-real-2026-09-25.md) | Um caso autorizado, documentos disponíveis, fontes, tempo e qualidade da minuta | Ao preparar e avaliar o primeiro caso real |
| [`produto/entrega-contexto-protocolo-2026-09-21.md`](produto/entrega-contexto-protocolo-2026-09-21.md) | Trabalho manual, evidências, pacote/comprovante, executor com simuladores e demonstração isolada | Para operar e implantar a entrega local de contexto e protocolo assistido |
| [`produto/plano-contexto-protocolo-2026-09-20.md`](produto/plano-contexto-protocolo-2026-09-20.md) | Plano executável sem acesso a tribunal: trabalho, evidências, minuta, pacote, comprovante e executor | Para a próxima sequência de implementação; contém aceites e dependências, não entregas concluídas |
| [`estado.md`](estado.md) | Status atual e próximos passos do MVP | Antes de qualquer decisão de produto/arquitetura |
| [`produto/execucao-2026-09-04.md`](produto/execucao-2026-09-04.md) | Implementação autorizada, validação, operação do upload e teste do Astra | Para usar e continuar a entrega de setembro |
| [`areas/diagnostico-causor-2026-09-04.md`](areas/diagnostico-causor-2026-09-04.md) | Diagnóstico do código, lacunas entre etapas, evidências e testes | Para distinguir implementação isolada de fluxo operacional |
| [`areas/pesquisa-mercado-2026-09-04.md`](areas/pesquisa-mercado-2026-09-04.md) | Concorrentes, fornecedores, APIs oficiais e correções das premissas antigas | Antes de escolher captura, protocolo ou posicionamento |
| [`produto/plano-evolucao-2026-09-04.md`](produto/plano-evolucao-2026-09-04.md) | Proposta de execução solo, critérios de piloto, features e avaliação do Astra | Para decidir e executar a próxima entrega |
| [`produto/PRD.md`](produto/PRD.md) | PRD estratégico, visão, mercado, features, roadmap | Para contexto de direção, não de implementação corrente |

## Operação

| Arquivo | O que tem | Quando ler |
|---|---|---|
| [`../RODAR-LOCAL.md`](../RODAR-LOCAL.md) | Quickstart para subir backend + frontend | Toda vez que for rodar localmente pela primeira vez no dia |
| [`operacao/local-dev.md`](operacao/local-dev.md) | Setup completo, troubleshooting e captura agendada local | Primeira instalação ou quando algo quebrar |
| [`operacao/deploy.md`](operacao/deploy.md) | Runbook de produção (envs, cron, provisionamento) | Ao publicar ou configurar ambiente definitivo |
| [`operacao/go-live.md`](operacao/go-live.md) | Estrutura pós-hospedagem: topologia, funil de vendas→conta, checklist de corte | Antes de hospedar e ao planejar o onboarding de produção |
| [`operacao/onboarding-piloto.md`](operacao/onboarding-piloto.md) | Fluxo de cadastrar o primeiro escritório/advogado | Ao onboardar um piloto |

## Áreas funcionais

| Arquivo | O que tem | Quando ler |
|---|---|---|
| [`areas/pje-assistido.md`](areas/pje-assistido.md) | Protocolo PJe assistido, vault, assinatura, como testar | Antes de mexer no conector PJe ou no fluxo de assinatura |
| [`areas/acesso-aos-autos-mercado.md`](areas/acesso-aos-autos-mercado.md) | Como Enter/Judit/Escavador resolvem o acesso aos autos e por que o Causor não deve copiá-los | Antes de decidir construir ou comprar camada de captura |
| [`areas/mni-credenciamento.md`](areas/mni-credenciamento.md) | Endpoints MNI verificados por varredura e o checklist do ofício de credenciamento | Ao registrar perfil MNI novo ou ao pedir acesso a um tribunal |
| [`areas/oficio-credenciamento-mni.md`](areas/oficio-credenciamento-mni.md) | Ofício de credenciamento redigido, com placeholders para preencher | Na hora de efetivamente pedir acesso à DTI de um tribunal |

## Agentes

| Arquivo | O que tem | Quando ler |
|---|---|---|
| [`../AGENTS.md`](../AGENTS.md) | Regras para agentes de IA (opencode, Claude Code) | Leitura obrigatória de todo agente antes de trabalhar no repo |
| [`../CLAUDE.md`](../CLAUDE.md) | Ponteiro para `AGENTS.md` | Compatibilidade com Claude Code |

## Histórico (não usar para inferir estado atual)

| Arquivo | O que tem | Quando ler |
|---|---|---|
| [`historico/README.md`](historico/README.md) | Aviso sobre a pasta histórica | Antes de abrir qualquer arquivo em `historico/` |
| [`historico/superpowers/`](historico/superpowers/) | Planos e specs antigos por data | Apenas para entender por que algo foi feito no passado |
| [`historico/2026-07-21-22-sessao-mni.md`](historico/2026-07-21-22-sessao-mni.md) | Registro da sessão que adotou o MNI e repriorizou as Tasks 6–9 | Para entender por que o roadmap mudou |
