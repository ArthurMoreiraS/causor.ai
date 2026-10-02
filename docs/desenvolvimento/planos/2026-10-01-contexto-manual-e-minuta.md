# Contexto manual e minuta recuperável

Retomada em nova conversa em 01/10/2026: fundador reforçou automação de
OAB → intimações/processos → prazo → trabalho/minuta com comunicação atual e
contexto do processo. Coordenador conferiu estado e diff antes da delegação;
alterações locais do bloco 4a foram preservadas para revisão por um executor
Sol/medium. Bloco 4b segue o contrato delimitado abaixo, após aceite do 4a.
Inventário de Computer Use nesta sessão retornou zero apps e browsers; não há
conferência visual disponível. Execução periódica de `capture-due` em produção
continua sem comprovação no registro atual; não confundir worker da fila com
agendador. Coleta automática de autos permanece meta dependente de canal e
inventário real, sem fornecedor contratado ou conector homologado.

Execução já autorizada no plano de 29/09. As correções de captura, prazo,
remoção de OAB e formulários foram implantadas em `cd09869`, com CI e deploy
aprovados. Este registro delimita a continuação das etapas 3 e 4.

## Etapa 3a: arquivos e ambientes

Um executor Sol implementa e testa identificação persistente do volume local,
identidade do bucket sem segredos, marcação dos jobs e seleção/recuperação
somente pelo worker correspondente. Jobs legados exigem acesso aos bytes.
Paginação deve alcançar jobs próprios atrás dos estrangeiros; a transação de
um store não pode bloquear jobs do outro. Testar dois stores e duas sessões
PostgreSQL em paralelo, além de reinício, recuperação e arquivo indisponível.
Arquivos: storage/objects.py, autos/service.py e worker.py, api/autos_routes.py
e testes diretamente relacionados. Não provisionar bucket nem migrar PDFs.

Implementada e revisada localmente em 01/10. Executor: 747 testes completos
aprovados/82 ignorados antes dos dois últimos casos de paginação/HEAD; 24 testes
finais aprovados, Ruff e diff check aprovados. Coordenador leu o diff e repetiu
34 testes de storage/upload/lease/recuperação/checkpoints, aprovados. Teste de
duas transações com stores distintos aguarda CI PostgreSQL descartável. Acesso
e reprocessamento de arquivo ausente respondem 409 com indicação do ambiente.

Publicada em `45ff3dd`: CI 36815849559 aprovado, incluindo PostgreSQL 16/17;
deploy 36815996053 aprovado e SHA conferido nos quatro serviços, com saúde
normal registrada pelo deploy. A consulta externa adicional foi bloqueada por
limite de uso da revisão automática de aprovação, sem execução da ação.

## Etapa 3b: preparar o contexto na tela de Trabalhos

Arquivos: TrabalhosView, WorkScope, WorkEvidence, DocumentUploadDialog,
ProcessContextStatus, work-api/api e testes frontend relacionados; office.css
somente para o layout desses componentes. Backend só se faltar contrato
necessário ao inventário, após decisão do coordenador.

Aceites:

- Processo capturado permite vincular ou cadastrar cliente na preparação;
  vínculo existente aparece e mudança exige intenção explícita. A falta de
  cliente ou polo aparece antes da geração, com caminho para resolver.
- Upload herda processo e grau do trabalho; destino fixo nessa entrada. O painel
  de contexto recebe o mesmo grau. Documento novo exige nova conferência.
- Três etapas visíveis: Objetivo, Documentos e contexto, Minuta e revisão.
  Busca e análise das fontes fazem parte da segunda etapa. Evitar criação
  duplicada de minuta ou campos repetidos.
- Campos não salvos de objetivo, escopo/índice e perguntas/fontes são protegidos
  ao trocar de módulo/trabalho ou receber polling; atualizar snapshot somente
  quando limpo. Remover remontagem de WorkScope por revisão. Conferência local
  perde validade quando snapshot das evidências muda.
- Resposta atrasada de busca ou ação não atualiza outro trabalho/consulta.
- Índice descreve peças, não exclui documentos da análise. Mostrar inventário
  e versões realmente usados e referências históricas do índice. Relatos e
  instruções do advogado aparecem como informações a conferir nas fontes.

Verificar `pnpm.cmd check`; testes devem exercer edição durante refresh,
troca de snapshot, busca atrasada, upload em grau 2 e cliente do caso capturado.
Build Linux no CI. DOM não comprova layout visual; navegador conectado ainda
indisponível no início deste bloco.

Implementada e revisada localmente: executor passou `pnpm.cmd check` (lint,
tipos e 144 testes em 27 arquivos); coordenador leu o diff e repetiu 28 testes
de WorkScope, WorkFlow, DocumentWorkflows e NoticeToWork, aprovados. Regressões
cobrem baseline com metadados reais, salvamento/resposta atrasados, fonte
fixada entre buscas, invalidação de conferência, cliente após refresh e polling
mais lento que cinco segundos. Conferência visual real permanece pendente.

Publicado em `602de50`: CI 36914544310 e deploy 36914779203 aprovados; SHA
conferido em backend/worker/autos-worker/frontend e saúde normal registrada
pelo deploy. Coordenador repetiu também os cinco testes de ProcessContextStatus,
totalizando 33 regressões repetidas. Não houve teste visual em navegador.

## Etapa 4: análise e redação recuperáveis

Antes da fila, fechar o contrato das fontes em um bloco 4a: incluir o teor da
intimação vinculada no objetivo da análise e na recuperação de fontes, sem
tratá-lo como prova dos fatos narrados. Guardar snapshot do teor/origem e
conferi-lo após a chamada e antes da revisão/redação. Usar também o histórico
SOR já disponível (movimentações, comunicações anteriores e peças), como
contexto suplementar identificado; a limitação de tamanho deve ficar explícita.
Minutas do próprio trabalho não entram nesse histórico suplementar: gerar a
peça não deve invalidar imediatamente as evidências que a originaram nem
transformar uma proposta anterior do modelo em prova. O helper de histórico
pode receber exclusão explícita do trabalho, preservando chamadas legadas.
Conferir snapshot desse histórico e dos metadados usados para não reaproveitar
análise de um estado anterior do processo. Prazo deve ter snapshot
de datas, duração, unidade, status e memória de cálculo; alterações durante a
redação impedem publicação. Prazo a revisar deve aparecer explicitamente como
provisório no contexto do redator, sem afirmação automática de tempestividade.
Aceites: provider simulado recebe comando atual e acervo; alteração do teor ou
prazo durante a chamada retorna conflito e não salva minuta; caso manual sem
intimação/prazo continua funcionando. Arquivos deste bloco: work_service.py,
service.py somente no helper de histórico, drafter.py se necessário ao contrato,
testes de trabalho/redação e respectivos
reusos PostgreSQL. Não mudar contratos de fila nem a UI nesse bloco.

No bloco 4b, executar o contrato de fila descrito abaixo com escopo delimitado
antes da delegação. Não confundir proteção contra resultado obsoleto com
recuperação após reinício: o bloco 4a continua usando HTTP síncrono.

Usar JobExecucao persistente para análise e geração, com identidade por tenant,
trabalho, versão, ação e solicitação. POST retorna acompanhamento; GET retoma
após refresh/perda de resposta; retry não duplica minuta. Worker usa lease
renovável e publicação condicionada à propriedade atual. Modelo roda fora da
transação e tem timeout. Recuperação nunca se aplica a envio judicial.

Guardar e conferir o snapshot do prazo, incluindo vencimento, parâmetros e
status; descartar resultado se prazo/contexto/objetivo mudar durante a chamada.
Registrar resultado e auditoria no mesmo commit. Preservar biblioteca legada e
conferência humana antes da redação. Instruções do advogado não equivalem a prova.

Arquivos a delimitar antes de delegar: agent/work_service.py e llm.py,
api/work_routes.py, queue e execução na API/CLI, frontend work-api/WorkEvidence,
schemas/settings e testes isolados/PG relevantes. Não adicionar integração de
tribunal nem alterar protocolo/assinatura.

Verificação: SQLite e providers simulados, concorrência PostgreSQL descartável,
Ruff, frontend check, CI e deploy. Teste integrado captura → prazo → upload →
extração/resumo → contexto → análise/conferência → minuta/edição/retomada.
Qualidade jurídica e integralidade real exigem revisão do advogado; nenhum
lote de produção ou chamada real de modelo será usado como teste.

## Revisão e publicação

Bloco 4a concluído e revisado localmente na retomada de 01/10. Coordenador leu
o diff dos três módulos e testes, repetiu 32 regressões de redação/fontes e os
22 testes de trabalho: 54 aprovados no total; Ruff e diff check aprovados.
Executor corrigiu frescor das leituras depois da chamada externa, incluiu
descrição/origem no snapshot de prazo e tornou explícito o corte de cada item
do histórico. Intimação atual entra uma vez; minutas do próprio trabalho não
retroalimentam as evidências. Prazo provisório é informado ao redator. Nenhum
provider real, caso real, PostgreSQL descartável ou deploy foi executado neste
bloco. Recuperação após reinício ainda depende do bloco 4b, agora em execução.

Retomada em 02/10 após interrupção do executor por limite de uso, sem perda
do diff. Sol/medium voltou a executar após novo pedido do fundador. Coordenador
repetiu 50 testes de work_jobs/legal_work/worker/llm, aprovados. O teste de
PostgreSQL acrescenta criação concorrente e dono antigo que retorna depois de
outro executor publicar. Execução local PG ainda indisponível; validação será
feita no CI descartável. Checks completos e percurso HTTP integrado permanecem
em execução. Não houve commit/deploy do bloco 4b até esse registro.

### Escopo de execução do bloco 4b

Revisado em 02/10: executor implementou e verificou 775 testes backend/97
ignorados na suíte completa, 54 direcionados após a correção final do token
original de aquisição, Ruff e frontend check (151 testes, lint e tipos).
Coordenador leu os diffs de fontes, fila, API, leases e UI; repetiu 54 testes
backend e 20 frontend, todos aprovados. Corrigida também a identidade original
entre commit e refresh, inclusive com expire_on_commit=True. Percurso HTTP
integrado usa captura/modelos simulados, PDF textual local e tmp_path; verifica
fonte e prazo no dossiê, retomada, retry sem duplicação e edição da peça.
PostgreSQL concorrente aguarda CI descartável; não houve acesso a autos reais,
chamada real de modelo ou validação de qualidade jurídica. Navegador integrado
indisponível na tentativa de 02/10. Publicação segue após esta revisão.

Após concluir/revisar 4a, um único executor pode alterar work_service.py
(somente hook de publicação/contrato de snapshot), llm.py (timeout de transporte),
work_routes.py, queue/worker.py, novo queue/work_jobs.py e módulo de lease de
trabalho, settings.py, work-api.ts, WorkEvidence.tsx e hook frontend próprio,
testes diretamente relacionados e reusos PostgreSQL. Não mudar filing, autos
lease, captura/prazo ou navegação geral. Preservar endpoints síncronos legados;
a tela passa a usar operações persistentes de análise/redação.

- POST de operação retorna 202 com job; GET atual/por ID retoma. Validar tenant,
  usuário, ação e versão; chave de solicitação repetida não duplica. Reutilizar
  operação ativa equivalente; dados divergentes geram conflito explícito.
  Serializar criação pela linha do trabalho. Retry de pedido concluído retorna
  seu resultado mesmo que a operação já tenha incrementado a versão.
- Guardar identidade dos inputs na solicitação; fonte/contexto/objetivo alterado
  enquanto enfileirado não é usado silenciosamente. Antes de publicar, validar
  novamente os snapshots do bloco 4a e propriedade do job.
- Worker dá prioridade a operação interativa depois da captura, antes do lote
  de prazos, para uma minuta não esperar centenas de classificações. Fila de
  documentos continua com consumidor próprio.
- Lease de trabalho tem token, expiração, heartbeat em transação separada e
  recuperação limitada a tipos de análise/minuta. Resultado de dono antigo
  não publica nem marca a execução do novo dono como falha. Não aplicar esse
  mecanismo a protocolo. Não registrar exceção bruta de provider em payload.
- Provider tem timeout/retry limitado. Modelo roda fora da transação. Domínio,
  resultado do job e auditoria ficam no mesmo commit final; falha desse commit
  não deixa uma minuta órfã marcada como sucesso.
- UI acompanha sem prender POST longo; refresh retoma job, falha permite
  tentativa explícita, conclusão recarrega trabalho. Não redigir duas peças por
  perda de resposta. Preservar perguntas/fontes sujas e ignorar resposta de
  outro trabalho. Edição local não é substituída pelo acompanhamento.

Verificação obrigatória: fakes/SQLite sem provider real, deduplicação/tenant,
mudança de input antes/durante execução, lease perdido/renovado/recuperado,
publicação e auditoria atômicas, navegação/refresh/perda de resposta na UI;
PostgreSQL concorrente no CI, Ruff, frontend check e integração do fluxo.

Um escritor por vez, sem subdelegação. Coordenador lê o diff e os resultados,
envia correções, registra limites e publica com autorização existente. Preservar
AGENTS.md e documentos não rastreados do fundador. Não apagar dados reais para
verificar remoção. Conferir SHA e saúde após deploy; não tratar isso como aceite
visual ou jurídico.
