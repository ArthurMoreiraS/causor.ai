# Documentação do Causor

| Arquivo | Para quê |
|---|---|
| [`estado.md`](estado.md) | Estado atual, evidências, o que falta para o MVP e próximos passos. Ler primeiro. |
| [`produto/direcao-pos-reuniao-2026-09-25.md`](produto/direcao-pos-reuniao-2026-09-25.md) | Direção de produto após a reunião com o advisor e ordem de execução. |
| [`produto/marco-caso-real-2026-09-25.md`](produto/marco-caso-real-2026-09-25.md) | Como avaliar o primeiro caso real e a ficha de resultado. |
| [`mercado/pesquisa-mercado-2026-09-04.md`](mercado/pesquisa-mercado-2026-09-04.md) | Concorrentes, fornecedores de autos e APIs oficiais. |

## Operação

| Arquivo | Para quê |
|---|---|
| [`operacao/aceite-mvp-2026-10-08.md`](operacao/aceite-mvp-2026-10-08.md) | Roteiro e registro do aceite do primeiro caso. |
| [`operacao/local-dev.md`](operacao/local-dev.md) | Rodar backend, workers e frontend na máquina; problemas comuns. |
| [`operacao/deploy.md`](operacao/deploy.md) | Produção na VPS: serviços, pipeline, logs, rollback e Caddy compartilhado. |
| [`operacao/captura-periodica.md`](operacao/captura-periodica.md) | Agendador de captura por OAB. |
| [`operacao/modelos-llm.md`](operacao/modelos-llm.md) | Modelos por tarefa, troca de provedor e salvaguardas da camada de IA. |
| [`operacao/onboarding-piloto.md`](operacao/onboarding-piloto.md) | Cadastrar escritório e advogado de um piloto. |

## Desenvolvimento

[`desenvolvimento/planos/`](desenvolvimento/planos/) guarda os planos em
andamento (escopo, aceite e verificação). Planos concluídos podem ser apagados
depois que `estado.md` refletir o resultado; o git preserva o histórico.

## Histórico

[`historico/`](historico/) guarda pesquisas superadas e trilhas adiadas (MNI,
PJe assistido, PRD de julho, log do estado até 06/10). Não usar para inferir o
estado atual.

Regras para agentes de IA: [`../AGENTS.md`](../AGENTS.md).
