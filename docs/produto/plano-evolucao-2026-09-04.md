# Plano de evolução: um fluxo útil, uma pessoa desenvolvendo

Data: 04/09/2026. Plano baseado no [diagnóstico do código](../areas/diagnostico-causor-2026-09-04.md) e na [pesquisa de mercado](../areas/pesquisa-mercado-2026-09-04.md). O fundador autorizou a execução; as entregas internas e a validação estão no [registro de execução](execucao-2026-09-04.md). Confirmou também que ainda não dispõe de acesso a tribunais. As etapas de piloto e homologação continuam dependentes dos recursos descritos abaixo.

**Primeiro resultado buscado:** um advogado consegue partir de uma intimação real e de documentos autorizados, revisar uma minuta fundamentada, exportar o pacote e registrar o resultado, sem depender do fundador para corrigir estados no banco.

Manter o objetivo de automatizar até o protocolo. Começar com envio manual assistido enquanto se valida um canal de execução. Investir em leitura automática e protocolo quando houver tribunal, tipo de ato e acesso concretos.

## 1. Recorte do piloto

O fundador desenvolve sozinho; quantidade de clientes e volume de trabalho são desconhecidos. O tribunal e a especialidade atuais não foram confirmados. Não dimensionar arquitetura para um número inventado nem escolher eproc/TJTO apenas porque consta em documentos antigos.

Buscar um advogado parceiro com disponibilidade para revisar exemplos. Fazer até cinco conversas curtas de descoberta, procurando uma família repetida de providências, processos acessíveis e dor mensurável. Não pedir a carteira inteira para começar.

Roteiro:

1. Percorrer as últimas cinco intimações e observar o que realmente foi feito.
2. Separar tempo de obter documentos, entender o caso, redigir, revisar e protocolar.
3. Registrar sistema, tribunal, grau, tipo de peça, documentos obrigatórios e exceções.
4. Pedir exemplos de minuta boa e ruim, com explicação das diferenças.
5. Verificar quem revisa, quem assina e o que o escritório já utiliza.

Escolher uma única família de providências pela frequência, disponibilidade de exemplos e possibilidade de revisão. Não presumir que toda intimação exige peça. Algumas geram tarefa, ciência, contato com cliente, audiência, cumprimento ou nenhuma ação imediata.

## 2. Ordem de execução

As janelas abaixo são limites de planejamento para um desenvolvedor com dedicação regular, não promessa de prazo. Se não couber, reduzir o escopo da entrega; não abrir várias frentes simultâneas.

| Etapa | Entrega | Critério de saída | Janela indicativa |
|---|---|---|---|
| 0 | Recorte e exemplos de referência | Um advogado, uma família de atos e casos autorizados | Primeira semana, junto às correções internas |
| 1 | Estado honesto e pipeline integrado | Upload HTTP chega a contexto utilizável sem intervenção no banco; UI mostra o estado real | Primeiros 5–10 dias úteis |
| 2 | Minuta com fontes e avaliação Astra/atual | Comparação cega e cronometrada em casos reservados; erros classificados | 1–2 semanas após etapa 1 |
| 3 | Piloto assistido | Advogado revisa, exporta e registra resultado em rotina real | 2–4 semanas de uso e ajustes |
| 4 | Um canal de automação | Cobertura demonstrada, pacote aprovado e recibo reconciliado | Somente após tribunal/acesso e decisão de canal |

Não encerrar uma etapa porque o calendário chegou ao fim. Registrar o que falhou e decidir entre corrigir, reduzir recorte ou descartar hipótese.

## 3. Backlog imediato, em ordem

IDs Dxx remetem aos achados do diagnóstico.

| Ordem | Trabalho delimitado | Aceite verificável |
|---|---|---|
| 1 | Filtrar jobs por consumidor e ligar extração → resumo → contexto (D01/D05) | Job documental não é consumido pelo worker errado; reinício retoma sem duplicar artefatos |
| 2 | Expor prontidão real e capacidades operacionais (D02/D03/D06) | Mesmo motivo e próxima ação na UI e no gate; login não habilita driver inexistente |
| 3 | Remover prazo fictício e representar pendência (D04) | Ato ambíguo ou sem prazo não gera vencimento de 15/1 dias; confirmação e origem ficam registradas |
| 4 | Corrigir alertas e saúde da captura (D11) | Simulação não conta como envio; falha/atraso gera sinal observável; retry não perde aviso |
| 5 | Versionar minuta, pacote e aprovação (D08) | Alterar texto/anexos/destino exige nova aprovação; job usa PDF exato aprovado |
| 6 | Corrigir semântica de protocolo (D09) | Registro manual não aparece como comprovante verificado; recibo tem estado e origem |
| 7 | Ligar evidências ao redator e à revisão (D07) | Fatos materiais abrem fonte por página; provas contrárias e lacunas aparecem para o advogado |
| 8 | Adapter Astra e medição por tarefa (D12) | Modelo, versão de prompt, consumo, latência e erros registrados; fallback configurável |
| 9 | Proteger auditoria e testar Postgres (D10) | Credencial operacional não altera/apaga log; isolamento, migrations e claims verificados no banco de produção equivalente |

Os itens 5, 6 e 9 devem estar concluídos antes de habilitar envio automatizado real. Um piloto exclusivamente assistido também precisa comunicar suas limitações e preservar o que foi aprovado.

Escolher testes pelos riscos: upload até contexto; fila concorrente; intimação sem prazo; edição após aprovação; recibo ausente; sessão interrompida depois de envio. Preservar os testes existentes sem confundir dublês de portal com homologação.

## 4. Experimento controlado com GPT-6 Astra

O teste útil deve responder duas perguntas separadas: **o modelo melhora a minuta com o mesmo contexto?** E **o contexto melhorado aumenta a qualidade, independentemente do modelo?**

A documentação oficial identifica `gpt-6-astra` e orienta Responses para ferramentas, além da remoção de `temperature`. Criar um adapter explícito, sem alterar o caminho padrão antes de avaliar. [Guia do Astra](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra).

A disponibilidade nesta conversa não confirma acesso pela API da empresa; são permissões distintas. Esse acesso não foi verificado nesta análise. [Disponibilidade por organização/projeto](https://learn.chatgpt.com/docs/enterprise/workspace-model-availability).

### Conjunto inicial

Começar com 30 casos autorizados, se o parceiro dispuser deles: 10 para ajustar e 20 reservados para avaliar. Com menos casos, tratar o resultado como exploração, não liberação para escala. Incluir casos com informação ausente, prova adversa, decisão antiga superada, digitalização ruim e comunicação sem petição cabível.

Fixar a fotografia de cada caso no momento da intimação. Excluir peças posteriores que revelem a resposta ou o resultado. Minutas históricas servem de referência ao revisor, não de entrada que entrega a resposta ao modelo. Agrupar processos relacionados no mesmo conjunto para evitar vazamento entre ajuste e avaliação.

Registrar, por caso, parte representada, providência correta, fatos materiais, fontes essenciais, pontos que não podem ser afirmados e regra de prazo revisada. Dados devem ficar no ambiente autorizado do escritório e não entrar no Git.

### Comparação

| Execução | Modelo | Evidências |
|---|---|---|
| A | Provider/modelo efetivamente usado hoje | Pacote de contexto atual |
| B | Astra | Exatamente o mesmo pacote de A |
| C | Modelo de A | Pacote aprimorado, com fatos e fontes relevantes |
| D | Astra | Mesmo pacote aprimorado de C |

Executar depois de conectar o pipeline mínimo. A não depende de reproduzir bugs impeditivos: o baseline deve ser um fluxo executável com os mesmos documentos. Alterações de adapter necessárias à compatibilidade ficam documentadas.

O advogado recebe saídas sem nome do modelo, em ordem aleatória. Registrar tempo de revisão até aprovação e motivo de rejeição. Usar avaliação automática para JSON, referências e regressões; ela não substitui o julgamento jurídico.

### Métricas e decisões

| Métrica | Como medir | Critério inicial proposto |
|---|---|---|
| Erro material | Fato, parte, pedido, prazo ou fundamento errado capaz de prejudicar o trabalho | Qualquer ocorrência bloqueia promoção até investigação |
| Apoio documental | Conferência dos fatos materiais contra fontes efetivas | Todos precisam de apoio ou identificação explícita como informação do cliente/hipótese |
| Omissão relevante | Comparação com checklist do advogado | Nenhuma omissão crítica na amostra de aceitação |
| Tempo ativo | Minutos do advogado até peça aceitável, incluindo conferência das fontes | Buscar redução de pelo menos 30% em relação ao seu fluxo atual |
| Aproveitamento | Peças aprováveis com edição localizada, sem reescrita substancial | Hipótese inicial de pelo menos 80% dentro do recorte |
| Custo | Dados + OCR + modelos + tentativas + intervenção | Medir por peça aprovada, não por chamada ou token isolado |
| Latência | Tempo total e por etapa | Mostrar mediana e pior caso da amostra; separar espera de trabalho ativo |

Esses percentuais são critérios propostos de decisão, não resultados obtidos. Vinte casos sem erro não demonstram segurança de 99% em produção. Repetir os casos difíceis, acompanhar falhas no piloto e ampliar a amostra antes de ampliar autonomia.

Se B melhora A, há ganho do modelo. Se C melhora A mais do que B, priorizar evidências. Se D oferece o melhor custo por trabalho aceito, liberar por feature flag para o piloto. Não considerar a confiança numérica que o modelo declara como probabilidade calibrada de acerto.

Para testar computer use separadamente, usar ambiente controlado de preparo: identificar processo, selecionar ato, anexar pacote e parar antes de envio. Comparar taxa de conclusão, cliques corretos, capacidade de parar diante de dúvida, latência e custo. Acesso aos portais e confirmação de protocolo são problemas distintos da qualidade da redação.

### Registro mínimo por execução

`case_id pseudonimizado`, snapshot dos autos, hash do pacote de evidências, modelo/provider reais, versão do prompt, configuração, tempo, consumo, status, referências emitidas, resultado do revisor e revisão aprovada.

Não registrar chaves, senhas ou sessões no prompt/log. Dados enviados à API OpenAI não são usados para treinamento por padrão, mas isso não equivale a zero retenção: controles e elegibilidade dependem de configuração, recursos e aprovação. Verificar a política aplicável ao ambiente usado. [Controles de dados](https://developers.openai.com/api/docs/guides/your-data).

## 5. Arquitetura mínima a preservar

Um backend modular, um banco Postgres e armazenamento privado bastam para esta fase. Persistir tarefas e versões permite retomar o trabalho sem introduzir várias plataformas de orquestração.

Contratos propostos:

- **Fonte de autos:** inventário, bytes, identidade externa, permissões conhecidas e data de coleta. Adapters de upload, fornecedor, MNI ou portal convergem no pipeline existente.
- **Evidências:** acervo completo dentro do escopo conhecido, índice, páginas, fatos, decisões e referências. Busca retorna fontes verificáveis.
- **Providência:** comunicação, ação necessária, responsável, prazo e pendências.
- **Minuta:** conteúdo versionado, análise, referências e lacunas.
- **Aprovação:** revisão e pacote exatos, aprovador e momento.
- **Execução:** destino, tentativa, estado, recibo e resultado reconciliado.

O modelo ajuda a interpretar, recuperar, redigir e revisar. Código controla transições, permissões, aritmética, hashes, aprovação e estado final. Um “agente universal” não deve substituir esses contratos.

## 6. Features com maior chance de valor

| Prioridade | Feature | Valor que precisa ser demonstrado |
|---|---|---|
| Agora | Minuta com fonte clicável ao lado | Reduzir o tempo para verificar um fato |
| Agora | Pendências documentais por providência | Saber qual documento falta e por que importa |
| Agora | Pacote para protocolo com PDF final e índice de anexos | Reduzir montagem, nomenclatura e conferência manual |
| Agora | Explicação do prazo e estado “a confirmar” | Evitar falsa certeza e revisão dispersa |
| Depois do primeiro piloto | Diferença desde a última leitura | Mostrar nova decisão/documento que muda o trabalho aprovado |
| Depois do primeiro piloto | Modelos e teses aprovados do escritório | Preservar estilo e estratégia sem transportar fatos entre clientes |
| Depois do primeiro piloto | Exportação DOCX e formatação institucional | Permitir trabalho no editor já adotado pelo advogado |
| Depois do primeiro piloto | Coleta organizada de subsídios do cliente | Resolver informação que não está nos autos |
| Sob demanda comprovada | Resumo de audiência, integração ao gestor existente e atualizações ao cliente | Expandir a partir do uso real, com dados e autorização apropriados |

Antes de exportar para tribunal, converter rótulos internos como `[DOC-12 p.3]` em referências compreensíveis ao destinatário, quando houver correspondência com evento/ID oficial. Preservar o mapa interno de fontes. PDF é artefato de apresentação: validar paginação, cabeçalho, tabelas, anexos e limites do destino, além do conteúdo.

Evitar agora: billing complexo, CRM completo, financeiro, jurimetria genérica, fine-tuning, banco vetorial separado e quatro famílias de conectores simultâneas. Podem ser úteis no futuro; hoje competem com fechar o fluxo central.

## 7. Cadência e decisões

Limite de trabalho em andamento: **uma entrega de produto**. Reservar uma parte pequena e fixa da semana para descoberta e comparação de fornecedores. Não abrir trabalho de tribunal sem um caso, conta e critério de aceitação.

Ao final de cada semana, registrar somente: caminho que funciona, evidência, falha principal, resultado percebido pelo advogado e próxima entrega. Atualizar `docs/estado.md`; planos antigos ficam como histórico. Não marcar tarefa concluída porque sua função passou isoladamente.

Promover o piloto quando o advogado completar o fluxo sem ajustes manuais do fundador, as pendências estiverem visíveis e a minuta poupar tempo. Promover automação de protocolo somente quando a rota escolhida produzir recibo reconciliado e tratar corretamente a queda após envio.

Se as minutas continuarem exigindo reescrita substancial, reduzir o recorte e corrigir a preparação das evidências. Se a minuta for boa e o gargalo for baixar documentos, comparar fornecedores. Se o tempo estiver concentrado no envio, priorizar um canal de protocolo. Deixar o comportamento observado decidir a próxima integração.
