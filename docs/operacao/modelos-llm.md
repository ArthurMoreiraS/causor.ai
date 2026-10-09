# Modelos do Causor

| Tarefa | Padrão |
| --- | --- |
| Chat e classificação/interpretação de comunicação | Haiku 4.5 |
| Resumo documental padrão | Haiku 4.5 |
| Resumo documental aprofundado, análise de evidências e minuta | Sonnet 5.5 |

O cálculo de datas permanece determinístico. No recebimento, escolher
**Resumo dos documentos → Aprofundado** para peças complexas. A escolha afeta
novos documentos/versões, aumenta o orçamento de saída e pode consumir mais
créditos. Resumos completos de arquivos idênticos continuam preservados; um
arquivo ainda em processamento mantém seu perfil e não recebe job duplicado.
Tentativas conservam o perfil no payload; modelo efetivo consta no resumo.
Ambos os perfis validam IDs e citações literais contra os trechos originais.

O deploy atualiza apenas configurações Claude ausentes ou Sonnet 5/4.6 legadas
para 5.5. Provedor/modelos personalizados permanecem intactos. Backup privado
`.env.pre-models`, troca atômica e permissão 600; segredos nunca entram no log.
Não voltar a configuração de banco/credenciais junto ao ajuste de um modelo.

## Comparação reproduzível

Casos JSONL autorizados: id, intimacao_texto, classificacao, contexto_processo;
histórico, prazo e template opcionais. Execute dentro de `backend`:

```powershell
./.venv/Scripts/python.exe -m app.agent.evaluate --cases artifacts/evals/casos.jsonl --output artifacts/evals/comparacao.jsonl --provider claude --claude-model claude-sonnet-5 --claude-model claude-sonnet-5-5 --limit 10
```

Cada modelo recebe a mesma entrada, identificada por hash. Saída registra
modelo, latência, minuta e consumo de tokens em `output.llm.usage`. Comando
faz chamadas cobradas; não executa automaticamente no CI. Material jurídico
deve ficar nos artifacts privados. Revisão humana deve medir fatos omitidos,
citações/contradições, correções exigidas e utilidade, além de custo e duração.

Em 06/10, um exemplo sintético passou nas APIs reais: Sonnet 5 em 23,1s
(1.851 tokens de entrada/1.707 de saída), 5.5 em 17,0s (1.853/2.157).
Resumo aprofundado 5.5 passou na conferência literal. Um caso não estabelece
superioridade jurídica, média de latência ou custo típico do produto.
[Migração oficial](https://platform.claude.com/docs/en/models/sonnet-5-5/migration-guide)
e [preços](https://platform.claude.com/docs/en/about-claude/pricing).

## Jev (em avaliação, fora da produção)

A Jev (TypeSafe AI) responde perguntas fechadas com probabilidades e não gera
texto. **Nenhuma rota do app a chama.** Existe só a bancada
`python -m app.agent.jev_bancada`, que compara as respostas dela com a análise
de prazo gravada ([plano](../desenvolvimento/planos/2026-10-09-jev-bancada.md)).
Chave em `CAUSOR_JEV_API_KEY`, lida na hora da chamada.

Medido em 09/10 sobre 90 intimações reais: 90/90 respondidas, mediana de
296 ms, 314.806 tokens de entrada, cerca de US$ 0,013 no total (US$ 0,00015
por intimação, com o preço publicado de US$ 0,042 por milhão de tokens de
entrada). Conferir o valor cobrado no console da TypeSafe. A qualidade
depende dos rótulos da bancada, ainda pendentes.

## Como a camada de IA funciona

O código vive em `backend/app/agent/`. A IA interpreta, resume e redige sobre o
contexto que o sistema determinístico já montou no SOR. Ela **não** calcula
datas (o `prazo_engine` conta; o prompt proíbe recalcular), **não** consulta
tribunal ou API externa e **não** recebe segredos.

| Arquivo | Responsabilidade |
|---|---|
| `llm.py` | Contrato `LLMProvider` e o ponto único de escolha do provedor, `get_provider()`. |
| `model_config.py` | Modelos por tarefa; o deploy usa este módulo para atualizar configurações legadas. |
| `classifier.py`, `deadline_interpretation.py` | Classificação da publicação e interpretação do prazo (dias, contagem). |
| `app/autos/summarizer.py` | Resumo dos documentos com citação literal conferida. |
| `evidence.py`, `context_selection.py`, `work_service.py` | Análise de evidências e seleção de contexto do trabalho jurídico. |
| `drafter.py` | Redação da minuta. |
| `assistant.py`, `chat_tools.py` | Assistente com ferramentas somente de leitura; propõe abrir um trabalho. |
| `evaluate.py` | Comparação reproduzível entre modelos (seção acima). |

### Provedor

`CAUSOR_LLM_PROVIDER` escolhe o provedor (`claude` é o padrão de produção).
Há overrides por tarefa (`CAUSOR_LLM_DRAFT_PROVIDER`,
`CAUSOR_LLM_CLASSIFICATION_PROVIDER`, `CAUSOR_LLM_CONTEXT_PROVIDER`), um
provedor `openai` (Responses API) e um `openai_compat` para Groq, OpenRouter ou
Ollama (`CAUSOR_LLM_BASE_URL`, `CAUSOR_LLM_API_KEY`, `CAUSOR_LLM_MODEL`,
`CAUSOR_LLM_MAX_TOKENS`). No `openai_compat`, um único modelo atende todas as
tarefas; serve para teste, não para medir qualidade jurídica. O assistente usa
sempre Claude, porque depende de tool use nativo.

### Salvaguardas

1. Segredos nunca entram em prompt ou log. O contexto enviado ao redator usa
   lista de campos permitidos; não fazer dump de modelos do SOR no prompt.
2. Prazo é determinístico; a IA só informa duração e tipo de contagem.
3. Citações de resumos e evidências são conferidas contra o texto original;
   citação inexistente invalida o resultado.
4. A minuta nasce como rascunho e só é aprovada por uma pessoa.
5. Testes do agente usam providers falsos, sem rede. Chamadas reais são
   opt-in e cobradas.
