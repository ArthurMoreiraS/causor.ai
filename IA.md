# IA no Causor — arquitetura, configuração e troca de provedor

Este documento descreve como a camada de IA do Causor funciona: qual modelo
faz o quê, onde está o ponto de troca (switch) entre Claude (produção) e
provedores gratuitos (teste), e o que todo dev precisa saber antes de mexer
nesa camada.

> **TL;DR para devs:** a IA nunca acessa sistemas externos direto. Ela só
> *interpreta/classifica/redige* sobre contexto que o sistema determinístico já
> montou no SOR. O switch entre Claude e modelo gratuito é **uma variável de
> ambiente** (`CAUSOR_LLM_PROVIDER`). Segredos (certificado, PIN, senha) nunca
> entram em prompt ou log.

---

## 1. Princípios de arquitetura

A arquitetura segue o padrão **SOR + conectores determinísticos + camada de
agente (LLM)**. A IA tem papel restrito e bem definido:

1. **Interpretar/classificar** o teor de uma intimação (tipo do ato, petição
   cabível, prazo em dias, úteis vs. corridos).
2. **Redigir** a minuta da petição a partir de um dossiê pré-montado
   (metadados, histórico, prazo já calculado, template do escritório).

O que a IA **não** faz:
- **Cálculo de prazo.** A data fatal é matemática determinística em
  `prazo_engine/deadline.py`. O LLM só diz *quantos dias*; o motor conta.
- **Captura de dados.** DJEN/DataJud são consumidos por `capture/` antes; o
  redator raciocina sobre o que já está no SOR, nunca "consulta" o tribunal.
- **Assinatura/protocolo.** O ato irreversível passa por gate humano; o
  certificado fica no PJeOffice local, fora do Causor.
- **Acesso a segredos.** Certificado, PIN, senha de assinatura vivem no vault;
  nunca entram num prompt.

---

## 2. Mapa de arquivos

Tudo da camada de IA vive em `backend/app/agent/`:

| Arquivo | Responsabilidade |
|---|---|
| `llm.py` | Transporte do modelo: contrato `LLMProvider`, `ClaudeProvider`, `OpenAICompatProvider` e o **switch** `get_provider()`. |
| `classifier.py` | Classifica o teor da intimação → `ClassificacaoIntimacao` (tipo, petição, prazo, confiança). |
| `drafter.py` | Redige a minuta → `MinutaGerada` (contexto consolidado, análise, minuta, alertas). |
| `service.py` | Orquestra o fluxo: enriquece processo via DataJud, classifica, calcula prazo, monta histórico e chama o redator. |
| `assistant.py` | Chat agentic com ferramentas (loop de tool-use). **Claude-only**, não usa o switch. |
| `chat_tools.py` | Ferramentas de leitura que o chat expõe ao LLM (listar prazos, processos, etc.). |

---

## 3. O contrato `LLMProvider` — o coração da troca

Em `agent/llm.py:29` existe um Protocol que define o que um provider precisa
saber fazer:

```python
class LLMProvider(Protocol):
    def complete_structured(...) -> BaseModel: ...  # classificar (devolve JSON validado)
    def complete_text(...) -> str: ...               # redigir (devolve texto)
```

Dois provedores concretos implementam o **mesmo contrato**:

- **`ClaudeProvider`** (`llm.py:39`): usa o SDK `anthropic`
  (`messages.parse` com `output_format=schema` para saída estruturada,
  `messages.create` com `thinking` adaptativo para texto). Lê
  `ANTHROPIC_API_KEY` do ambiente.
- **`OpenAICompatProvider`** (`llm.py:83`): chama qualquer endpoint
  compatível com a OpenAI Chat Completions API (Groq, OpenRouter, Gemini
  OpenAI-compat, Ollama local) via `httpx`. Saída estruturada por
  *JSON-mode prompting + validação Pydantic* (sem depender de API
  vendor-específica de tool/parse, então funciona em qualquer endpoint).

Como ambos cumprem o mesmo contrato, `classifier.py` e `drafter.py` não sabem
(nem precisam saber) qual provedor estão usando.

---

## 4. O switch — uma variável liga/desliga

O ponto **único** de decisão é `get_provider()` em `llm.py:199`:

```python
def get_provider(*, model=None) -> LLMProvider:
    provider = (settings.llm_provider or "claude").strip().lower()
    if provider == "openai_compat":
        return OpenAICompatProvider()   # → Groq/Ollama (HTTP)
    return ClaudeProvider(model=model)  # → Anthropic SDK
```

Quem chama essa porta (apenas dois lugares no fluxo principal):

- `classifier.py:39` → `get_provider(model=settings.claude_classification_model)`
- `drafter.py:85` → `get_provider(model=settings.claude_draft_model)`

### 4.1 Produção (Claude)

No `.env` do backend:

```bash
CAUSOR_LLM_PROVIDER=claude        # ou simplesmente não definir (default)
ANTHROPIC_API_KEY=sk-ant-...      # lida direto pelo SDK Anthropic
```

### 4.2 Teste gratuito (Groq)

> **Nota (07/07/2026):** o switch existe e é testado (`test_llm.py`), mas
> **não é a prática atual** de desenvolvimento/teste do time — testes também
> rodam com Claude, para manter a qualidade de classificação/redação
> consistente com produção. Esta seção documenta a capacidade, não um fluxo
> recomendado no momento.

```bash
CAUSOR_LLM_PROVIDER=openai_compat
CAUSOR_LLM_BASE_URL=https://api.groq.com/openai/v1
CAUSOR_LLM_API_KEY=gsk_sua_chave_gratuita
CAUSOR_LLM_MODEL=llama-3.3-70b-versatile
```

### 4.3 Teste local (Ollama, sem internet)

```bash
CAUSOR_LLM_PROVIDER=openai_compat
CAUSOR_LLM_BASE_URL=http://localhost:11434/v1
CAUSOR_LLM_API_KEY=
CAUSOR_LLM_MODEL=llama3.1:8b
```

> A chave do Claude (`ANTHROPIC_API_KEY`) pode **permanecer no `.env`** mesmo
> em modo de teste — ela simplesmente não é chamada nesse caminho. Não é
> preciso apagar nada para alternar; basta trocar
> `CAUSOR_LLM_PROVIDER`.

---

## 5. Knobs de configuração (`settings.py`)

| Variável | Default | Efeito |
|---|---|---|
| `CAUSOR_LLM_PROVIDER` | `claude` | `"claude"` → SDK Anthropic; `"openai_compat"` → endpoint HTTP. |
| `CAUSOR_LLM_BASE_URL` | `""` | Base do endpoint OpenAI-compat (ignorado em modo Claude). |
| `CAUSOR_LLM_API_KEY` | `""` | Bearer token do provedor (`""` = sem auth, p/ Ollama local). |
| `CAUSOR_LLM_MODEL` | `""` | Nome do modelo no provedor (ignorado em modo Claude). |
| `CAUSOR_LLM_MAX_TOKENS` | `4000` | Teto de tokens de saída **só no openai_compat**. Evita `413` em modelos de contexto menor. `0` = respeita o valor pedido pelo caller. |
| `CAUSOR_CLAUDE_*` | ver abaixo | Modelos Claude por tarefa (chat/classificação/redação). |

Modelos Claude por tarefa (afinados para custo/benefício):

| Setting | Default | Uso |
|---|---|---|
| `claude_chat_model` | `claude-haiku-4-5` | Chat agentic (barato, rápido). |
| `claude_classification_model` | `claude-haiku-4-5` | Classificar intimação (barato). |
| `claude_draft_model` | `claude-sonnet-4-6` | Redigir minuta (qualidade jurídica). |
| `claude_model` | `claude-sonnet-4-6` | Fallback geral. |

> Os modelos `claude_*` só são lidos pelo `ClaudeProvider`. No modo
> `openai_compat`, todo o pipeline usa **um único** `CAUSOR_LLM_MODEL`
> (suficiente para teste).

---

## 6. Fluxo de geração de minuta (o que o dev precisa ver)

Entrada: uma `Intimacao` com `teor`. Saída: `Prazo` + `Peticao` (rascunho).

`service.py:230` — `draft_from_intimacao`:

1. **Valida** que a intimação tem texto (`teor`).
2. **Enriquece on-demand** via DataJud se o processo ainda não tem andamentos
   nem metadados (`_ensure_enriched`). Falha de DataJud **não bloqueia**.
3. **Classifica** o teor (`classify_intimacao`) → `ClassificacaoIntimacao`
   com `tipo`, `peticao_sugerida`, `prazo_dias`, `dias_uteis`, `confianca`.
4. **Calcula o prazo** de forma determinística
   (`registrar_prazo` → `compute_deadline`). O LLM só informou os dias; a
   data fatal é matemática.
5. **Busca o template** do escritório pro tipo de petição (`_template_for`).
6. **Monta o dossiê** e chama o redator (`draft_peticao`):
   - `contexto_processo`: número, classe, tribunal, órgão julgador (whitelist
     de chaves não-sensíveis).
   - `historico`: andamentos do DataJud + intimações anteriores + petições
     anteriores do escritório, com truncamento e limite de itens.
   - `prazo_fatal`: a data já calculada (o prompt diz explicitamente "NÃO
     recalcule").
   - `template_conteudo`: estrutura do escritório a preservar.
7. **Persiste** a `Peticao` com `status="rascunho"` e um `dossie` (contexto,
   análise, alertas, confiança) para apoiar a revisão humana.

### 6.1 Contexto é completo, não só a intimação

O redator recebe o processo inteiro, não apenas a instância da intimação.
O `_historico_processo` (`service.py:53`) puxa do SOR:

- Movimentações do DataJud (mais recentes, com limite e truncamento).
- Intimações anteriores do mesmo processo.
- Petições anteriores do escritório no processo.

Tudo é texto determinístico, pré-montado — o LLM não "consulta" nada em
tempo de redação.

---

## 7. Por que o chat não troca

`assistant.py` **não** passa por `get_provider()`. Ele importa `anthropic`
direto e faz um loop de tool-use (ferramentas de leitura em `chat_tools.py`).
Isso é propositivo: o chat agentic precisa de tool-calling nativo do Claude,
que é mais complexo de replicar num endpoint OpenAI-compat.

- **Fluxo principal** (captura → classificar → redigir minuta → protocolar):
  segue o switch.
- **Chat**: sempre Claude, independente do switch.

Se um dia for preciso chat no provedor gratuito, é uma peça separada (loop de
tool-use adaptado para function-calling do endpoint).

---

## 8. Salvaguardas que o dev NÃO deve quebrar

1. **Segredos nunca em prompt/log.** O `_ALLOWED_CONTEXT_KEYS` em
   `drafter.py:23` é uma whitelist — nunca faça dump de um `processo.__dict__`
   ou de uma `CredencialAssinatura` no prompt. Certificado/PIN/senha ficam no
   vault.

2. **Prazo é determinístico.** O LLM só diz os dias; a data fatal vem do
   `prazo_engine`. O prompt do redator proíbe recalcular. Nunca peça ao LLM
   para somar datas.

3. **Coerção de `prazo_dias`.** Modelos fracos podem devolver `prazo_dias=0`,
   que o motor rejeita (`deadline.py:40`, `days must be >= 1`). O
   `ClassificacaoIntimacao` em `classifier.py` tem um `field_validator` que
   coercion `< 1` para `1`, mantendo o fluxo vivo. Não remova essa coerção
   sem substituí-la por outra defesa de fronteira.

4. **Teto de tokens no teste.** O drafter pede `max_tokens=8000` (afinado
   pro Claude). Modelos gratuitos de contexto menor devolvem `413 Payload
   Too Large`. O `OpenAICompatProvider._cap_tokens` aplica
   `CAUSOR_LLM_MAX_TOKENS` (default 4000). Só afeta o provider de teste; o
   Claude ignora.

5. **Gate humano antes do irreversível.** A minuta é sempre `rascunho`. O
   protocolo exige `aprovada`. Nunca deixe a IA pular o gate.

---

## 9. Testando a camada de IA

Os testes em `backend/tests/` cobrem o agente **sem rede real**:

- `test_llm.py`: `ClaudeProvider` com cliente fake; `OpenAICompatProvider`
  com `httpx_mock`; asserções do switch e do teto de tokens.
- `test_agent.py`: classificação + redação com `_FakeProvider`; coerção de
  `prazo_dias`; segredos não vazam no prompt.

Para validar com um modelo real gratuito, basta configurar `openai_compat`
no `.env` e disparar uma geração de minuta pela API/UI. Se o modelo for
fraco demais para classificar, o `LLMProviderError` (JSON inválido / schema
inválido) sinaliza explicitamente — falha *fail-loud*, nunca silenciosa.

---

## 10. Receitas rápidas

### Voltar pra Claude (produção)

```bash
# .env do backend
CAUSOR_LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
```

Reinicia o backend. Pronto.

### Testar de graça com Groq

```bash
CAUSOR_LLM_PROVIDER=openai_compat
CAUSOR_LLM_BASE_URL=https://api.groq.com/openai/v1
CAUSOR_LLM_API_KEY=gsk_...
CAUSOR_LLM_MODEL=llama-3.3-70b-versatile
CAUSOR_LLM_MAX_TOKENS=4000
```

### Ainda dá 413 no Groq?

Baixe o teto: `CAUSOR_LLM_MAX_TOKENS=2000`.

### Adicionar um novo provedor de teste

Implemente o contrato `LLMProvider` em `llm.py` e ramifique em
`get_provider()`. Não toque em `classifier.py`/`drafter.py` — eles só
dependem do contrato.
