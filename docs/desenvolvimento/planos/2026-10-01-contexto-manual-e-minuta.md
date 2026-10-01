# Contexto manual e minuta recuperável

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

Um escritor por vez, sem subdelegação. Coordenador lê o diff e os resultados,
envia correções, registra limites e publica com autorização existente. Preservar
AGENTS.md e documentos não rastreados do fundador. Não apagar dados reais para
verificar remoção. Conferir SHA e saúde após deploy; não tratar isso como aceite
visual ou jurídico.
