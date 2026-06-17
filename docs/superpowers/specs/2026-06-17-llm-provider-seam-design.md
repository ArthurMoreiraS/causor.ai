# Design — Camada de provider LLM plugável (Gemini default, Claude selecionável)

> 2026-06-17. Aprovado pelo usuário. Gemini é provisório; o desenho prioriza
> trocar de modelo no futuro com mudança mínima.

## Problema

`classifier.py` e `drafter.py` chamam o SDK Anthropic (Claude) hardcoded. A
conta Claude está sem créditos, então `POST /intimacoes/{id}/draft` falha (503).
O usuário quer rodar essas duas tarefas no Gemini agora, sabendo que vai trocar
de modelo de novo no futuro.

## Objetivo

Mover classificação e redação de minuta para um **seam de provider plugável**,
com Gemini (`gemini-2.5-flash`) como padrão e Claude mantido como provider
selecionável via configuração. Adicionar um terceiro modelo no futuro deve ser
uma classe nova + uma linha na fábrica + uma env var — nenhum caller muda.

## Arquitetura

Novo módulo `app/agent/llm.py` com duas capacidades (apenas essas — YAGNI):

```python
class LLMProvider(Protocol):
    def complete_structured(self, *, system: str, user: str,
                            schema: type[BaseModel]) -> BaseModel: ...
    def complete_text(self, *, system: str, user: str, max_tokens: int) -> str: ...
```

- `complete_structured` — classificação (saída estruturada/JSON validada por pydantic).
- `complete_text` — redação de minuta (texto livre).

### Implementações

- **`GeminiProvider`** (padrão) — via `google.genai`.
  - structured: `generate_content(config={response_mime_type:"application/json",
    response_schema: schema, system_instruction})` → `response.parsed`.
    Clampa defensivamente campos float fora de faixa antes de validar (ver caveat).
  - text: `generate_content` → concatena partes de texto.
  - modelo default `gemini-2.5-flash` (configurável).
- **`ClaudeProvider`** — move a lógica Claude atual.
  - structured: `messages.parse(... output_format=schema, thinking={"type":"adaptive"},
    output_config={"effort":"high"})` → `parsed_output`.
  - text: `messages.create(... thinking adaptive, effort high)` → texto.
  - modelo default `claude-opus-4-8`.

### Fábrica

`get_provider(name: str | None = None) -> LLMProvider` lê `settings.llm_provider`
(default `"gemini"`). `"gemini"`→Gemini, `"claude"`→Claude, desconhecido→`ValueError`
claro. Clients dos SDKs são instanciados lazy dentro de cada provider e
injetáveis nos testes.

## Settings (`app/settings.py`)

- `llm_provider: str = "gemini"` → `CAUSOR_LLM_PROVIDER`
- `gemini_model: str = "gemini-2.5-flash"` → `CAUSOR_GEMINI_MODEL`
- `claude_model: str = "claude-opus-4-8"` → `CAUSOR_CLAUDE_MODEL`

## Callers (finos; domínio permanece neles)

- `classifier.py`: mantém `_SYSTEM` + pydantic `ClassificacaoIntimacao`; assinatura
  passa a `classify_intimacao(texto, *, provider=None)` e chama
  `provider.complete_structured(system=_SYSTEM, user=..., schema=ClassificacaoIntimacao)`.
- `drafter.py`: mantém montagem do prompt + **whitelist anti-vazamento de segredo**;
  assinatura `draft_peticao(..., provider=None)` e chama
  `provider.complete_text(system=_SYSTEM, user=prompt, max_tokens=8000)`.
- `agent/service.py`: sem mudança (não passa client hoje).

## Fora de escopo

- `assistant.py` (chat) já roda no Gemini com tool-use — não muda agora; pode
  adotar o mesmo seam depois.
- Filing/protocolo continua determinístico, atrás do gate humano.

## Erro / degradação

`POST /intimacoes/{id}/draft` já encapsula falhas em 503. Com Gemini default e
`GEMINI_API_KEY` carregada no boot (load_dotenv), passa a funcionar. Provider sem
chave → erro claro → 503.

## Caveat técnico

O JSON-schema do Gemini ignora restrições pydantic como `ge/le` (campo
`confianca`). Se o modelo devolver valor fora de [0,1], `.parsed` falharia.
Mitigação: o `GeminiProvider` clampa campos numéricos conhecidos para a faixa
válida antes de instanciar o schema. Coberto por teste.

## Testes (TDD)

- **Novo `tests/test_llm.py`**: `get_provider` (default Gemini, Claude por config,
  erro em desconhecido); `GeminiProvider.complete_structured`/`complete_text` com
  client `genai` fake (inclui clamp do `confianca`); `ClaudeProvider` idem com
  client `anthropic` fake — herda as asserções de model/thinking/effort hoje em
  `test_agent.py`.
- **`tests/test_agent.py` reescrito**: injeta um **provider fake** e mantém os
  testes de domínio — texto da intimação chega no prompt, retorno
  estruturado/texto, e o crítico `test_draft_never_leaks_secrets`.

## Arquivos

- Novos: `app/agent/llm.py`, `tests/test_llm.py`
- Modificados: `app/agent/classifier.py`, `app/agent/drafter.py`,
  `app/settings.py`, `tests/test_agent.py`, `backend/.env.example`
