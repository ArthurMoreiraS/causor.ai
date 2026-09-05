# Documentos e evidências: biblioteca e recebimento por tarefa

O fundador autorizou implementar o próximo bloco do escritório integrado.
Esta entrega permite consultar o acervo, conferir uma fonte e receber o
documento solicitado numa pendência, usando o processamento já existente.

## Fluxo disponível

1. **Documentos e evidências**, no grupo Escritório, lista arquivos com busca
   por nome, filtro por processo e paginação no servidor. Mostra cliente,
   grau, extração, resumo e inclusão no conjunto atual de documentos.
2. **Conferir evidências** abre a versão selecionada, resumo, citações, busca
   nos trechos extraídos e PDF na página escolhida. Há paginação de versões
   e de trechos. A versão citada pode ser histórica e permanece selecionada
   mesmo quando existe um arquivo mais recente. Conteúdo HTML não é embutido
   como PDF; o download autenticado confere o hash da versão.
3. Em **Tarefas e pendências → Documentos da pendência**, receber arquivos
   mantém uma referência à versão exata, nome e hash recebidos. O formulário
   confere processo, grau e a versão da tarefa aberta pelo usuário.
4. O recebimento move a tarefa para **Em andamento** e registra auditoria.
   O advogado confere o documento e conclui a pendência explicitamente.
   A tarefa pode nascer apenas com cliente; ao receber, associa-se a um
   processo compatível com esse cliente. Não é criado um processo fictício.
5. As fontes da minuta abrem o mesmo visualizador sem descartar a edição.
   O detalhe do processo/intimação também oferece acesso à biblioteca.

## Envio complementar e contexto

O envio da biblioteca usa `complementar=true` no upload. Preserva os itens
verificados da última captura completa e acrescenta os arquivos recebidos.
Um nome já enviado por upload reutiliza o documento lógico e versiona o
conteúdo por hash; reenviar bytes idênticos reutiliza a mesma versão.
Não é necessário baixar ou reprocessar os arquivos preservados.

Se a captura anterior do grau estiver incompleta, em andamento ou declarada
não aplicável, o complemento é recusado com orientação para corrigir o
escopo anterior. Sem captura anterior, o recebimento inicia o conjunto
declarado daquele grau. Completude e suficiência jurídica não são inferidas
do simples recebimento. O manifesto complementar guarda a referência à
captura anterior e sua fonte; não converte documentos do cliente em prova
de captura integral do tribunal.

O novo manifesto muda o fingerprint. Arquivos novos entram na fila de
extração/resumo e o contexto só fica disponível após as verificações normais.
Minutas existentes não são reescritas nem aprovadas automaticamente. O teste
de processamento demonstra a passagem disponível → pendente → disponível
com dois documentos, preservando o resumo do primeiro arquivo.

O upload tradicional dos autos mantém a substituição do inventário declarada
na interface. Dentro da biblioteca, o botão do painel de contexto abre o
formulário complementar, inclusive com vínculo da tarefa quando presente.

## Persistência e integridade

Migração `a7d3f9b5c1e4`, após `a6c2e8f4b0d3`, cria `tarefa_documento`.
Recebimentos têm unicidade por tarefa/versão. Se a origem for removida, FKs
`SET NULL` preservam o registro do recebimento. A remoção da OAB continua
preservando tarefas e auditoria; não há exclusão física nova de objetos.

Capturas do mesmo processo são serializadas para impedir gerações concorrentes
que descartem arquivos de um dos envios. Tarefa encerrada ou alterada durante
a revisão devolve conflito. Processo/tarefa de outro escritório é recusado.
Upload e recebimento usam a mesma transação: lote inválido não muda tarefa,
inventário ou contexto no banco. Objetos eventualmente gravados antes de um
rollback seguem a política existente de retenção do storage.

Novos jobs documentais incluem o escritório no payload, para que a limpeza de
OAB possa identificá-los. A biblioteca só publica metadados selecionados;
chaves internas de armazenamento não são devolvidas nas respostas de listagem.
O upload aceita até 50 arquivos por lote, com o limite por arquivo já
configurado, e recusa nomes vazios ou acima de 255 caracteres.

## Validação e limites

Validação local: **682 testes de backend aprovados, 55 pulados**, **79 testes
de frontend**, Ruff, ESLint, TypeScript e `git diff --check` aprovados.
Os 55 pulados são 49 cenários PostgreSQL (executados na matriz do CI) e seis
opt-in. Após ajustes finais de integridade, 25 testes de biblioteca/upload
foram repetidos com sucesso. Testes HTTP cobrem preservação de inventário,
versões, vínculo, conflito, rollback e processamento com provedor simulado.
O CI também inclui dois complementos simultâneos no PostgreSQL.
O reenvio de versão processada foi testado: a contagem inclui o item recebido
e não há nova chamada de extração/IA para os mesmos bytes já processados.

O [CI da versão 8e94063](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/33949623232)
aprovou **682 testes gerais backend, 79 frontend e 49 em cada PostgreSQL
(16/17)**, além de lint, tipos e build de produção no Linux. A migração real
e os complementos concorrentes passaram nos dois bancos.

A primeira tentativa de implantação falhou antes dos comandos remotos:
timeout ao conectar à porta SSH da VPS. Não houve migração ou troca de
serviços nessa tentativa. A integração GitHub recusou o re-run com HTTP 403
por falta de permissão de Actions. A segunda tentativa usou o fluxo normal
de push/CI/deploy, com a mesma implementação e este registro de validação.

O [novo CI](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/33950004436)
aprovou novamente. O [deploy de `7aacbf2`](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/33950069870)
concluiu em 05/09/2026 às 03h37 (Brasília): migração `a7d3f9b5c1e4` aplicada,
backend, worker, autos-worker e frontend saudáveis, com a versão exata
`7aacbf245bd4d63f5d70e8b33cc5052fc08b9e00` verificada nos quatro serviços.

Ainda não foi possível validar visualmente: o inventário de navegadores da
sessão continuou vazio. O frontend foi implementado com os componentes e
tokens existentes; testes de interação não substituem essa conferência.
Não houve chamada paga de IA, envio a tribunal ou uso de autos reais.

## Próximo aceite com o advogado

Escolher um caso autorizado e receber um documento solicitado por tarefa.
Conferir a versão recebida, o texto extraído, a citação no PDF e a próxima
minuta. Registrar se o documento necessário estava disponível, se a redação
o utilizou corretamente e o tempo de correção. Repetir até cinco casos antes
de afirmar ganho de qualidade. Pacote de peça/anexos para protocolo e
homologação de um canal judicial continuam nas próximas entregas.
