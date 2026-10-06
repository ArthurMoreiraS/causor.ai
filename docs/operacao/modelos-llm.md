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
