# Integração back ↔ front + chat agêntico — Design

**Data:** 2026-06-10
**Branch:** `feat/mvp-captura-prazo-engine`
**Status:** aprovado (aguardando plano de implementação)

## Objetivo

Fechar os gaps de integração entre backend e frontend nos dois sentidos (back exposto que o
front não usa; front que referencia coisas inexistentes no back) e tornar o produto o mais
"AI-driven" possível, no espírito do Handle.ai. A peça central é um **assistente conversacional
agêntico** que lê o SOR e propõe ações do fluxo, sempre preservando o gate humano.

## Contexto / gaps identificados

Backend existe, front não usa:
- `POST /capture/oab` (captura real por OAB) — front só chama `/capture/demo`.
- `PATCH /prazos/{id}` (revisar prazo) — sem UI.
- `DraftResponse.classificacao` (tipo/confiança da IA) — `gerarMinuta` descarta (`void`).

Schema existe, falta endpoint + UI:
- `AuditLogOut` — sem `GET /audit`; nav "Auditoria" é link morto.
- `ChatRequest/Response` + `app/agent/assistant.py` — sem rota `/chat` e sem painel no front.

Front referencia mas não existe:
- Itens do nav lateral (`Processos`, `Intimações`, `Prazos`, `Auditoria`, etc.) são `href="#"`.

## Decisões tomadas (com o usuário)

- Tudo num único spec (buckets A–E).
- Chatbot **fica** (inspirado no Handle.ai; usuário usará modelo mais barato depois — não otimizar por modelo agora).
- Chat é **agêntico com tool-use**: lê o SOR e **propõe** ações do fluxo (`gerar_minuta`,
  `marcar_prazo_cumprido`, `aprovar_peticao`). Nunca protocola.
- Ações que mudam estado **nunca** são executadas direto pelo modelo: viram *propostas* que o
  advogado confirma; a execução real usa os endpoints REST já existentes, auditada como `usuario:N`.
- Conversas são **stateless**: o front mantém o histórico e reenvia a cada turno. As ações
  disparadas continuam auditadas no SOR. Sem migration nova.

## Abordagem do chat agêntico

Loop de tool-use roda no **backend** (`POST /chat`):
- Ferramenta de **leitura** chamada → backend executa contra o SOR (com a `Session`) e devolve o
  resultado ao modelo; o loop repete até a resposta final.
- Ferramenta de **ação** chamada → backend **não executa**; captura como *ação proposta* e devolve
  na resposta. O front renderiza card "Confirmar / Descartar"; ao confirmar, chama o endpoint REST
  existente. `protocolar` não é exposto como ferramenta.

Alternativas descartadas: orquestrar o loop no front (vaza lógica de agente, muitos round-trips);
agente executa tudo com gate só no protocolo (viola "sempre via gate humano").

Justificativa: gate intacto, reuso dos endpoints existentes para execução real, segredos/sessão no
servidor, front só renderiza texto + cards.

## Componentes

### 1. Backend — chat agêntico
- `app/agent/assistant.py` evolui de "uma resposta" para um **loop de tool-use** com um registry de
  ferramentas. Ferramentas de leitura recebem a `Session`; ferramentas de ação são declaradas ao
  modelo mas interceptadas (retornam proposta, não efeito). Whitelist de contexto mantida.
- `POST /chat`: recebe `messages` + `processo_id?`; roda o loop; responde
  `{ reply, proposed_actions[], tool_trace[] }`, onde
  `proposed_actions = [{ tipo, label, endpoint, payload }]`.
- Erro de IA → 503 com mensagem clara (mesmo padrão de `gerar_minuta`).

### 2. Backend — fechar gaps órfãos
- `GET /audit`: lista `AuditLog` (filtros `entidade`, `entidade_id`, `limit`) via `AuditLogOut`.
- `POST /capture/oab` — sem mudança (só consumo no front).
- `PATCH /prazos/{id}` — sem mudança (só consumo no front).
- `gerar_minuta` já devolve `classificacao` — só falta o front consumir.

### 3. Frontend — `lib/api.ts`
- `enviarMensagemChat(messages, processoId?)` → `/chat`.
- `rodarCapturaOab(oab, uf, ...)` → `/capture/oab`.
- `revisarPrazo(id, patch)` → `PATCH /prazos/{id}`.
- `carregarAuditoria(filtros)` → `/audit`.
- `gerarMinuta` passa a **retornar** a `classificacao` (deixa de ser `void`).

### 4. Frontend — superfícies novas
- **Painel de assistente** dockável à direita (estilo copiloto): histórico em estado local, input,
  render de `proposed_actions` como cards "Confirmar / Descartar". Contexto = processo selecionado.
- **Captura real**: modal com OAB/UF/datas ao lado do "Rodar captura" (demo vira secundário).
- **Auditoria**: painel/aba lendo `/audit`, fechando o nav morto.
- **Surfacing de IA**: badge de tipo + % de confiança no card da petição após `gerarMinuta`.
- **Fora de escopo:** roteamento para todos os itens do nav (Calendário etc.). Só as superfícies
  com backend real agora.

## Constraints honrados

- **Gate humano:** ações do chat sempre confirmadas pelo usuário; `protocolar` nunca é ferramenta.
- **Segredos fora do prompt:** whitelist mantida também nas ferramentas de leitura.
- **Trilha imutável:** toda ação confirmada via chat é auditada com `ator=usuario:N`.
- **APIs oficiais antes de scraping:** sem mudança nessa camada.

## Testes (TDD)

- Loop de tool-use com client Anthropic mockado: leitura executa contra SOR; ação vira proposta.
- `POST /chat`: happy-path; erro de IA → 503.
- Gate: `protocolar` nunca aparece entre as ferramentas expostas ao modelo.
- `GET /audit`: filtros por `entidade`/`entidade_id`/`limit`.
- Suíte atual permanece verde; `ruff` limpo nos arquivos tocados.

## Build order

Back (ferramentas + `/chat` + `/audit`, TDD) → `lib/api.ts` → superfícies de front
(assistente, captura OAB, auditoria, surfacing de IA).
