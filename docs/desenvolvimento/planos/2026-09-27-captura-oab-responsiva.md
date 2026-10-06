# Captura por OAB com acompanhamento e recuperação

Estado: implantado (`cab194d`) em 28/09; feedback adicional em plano de 29/09.

## Contexto e escopo

O usuário relata captura presa no modal e animações paradas. A tela chama
`rodarCapturaOab`: cadastro seguido de `POST /capture/oab` síncrono e refresh
completo antes de liberar o estado ocupado. `request` não possui limite de
espera, inclusive na consulta da sessão. DJEN usa timeout de 120s e até cinco
tentativas; o resultado não é visível enquanto a chamada inteira não termina.
Existe fila persistente (`POST /jobs/capture/oab`, `GET /jobs/{id}`) e worker
implantável com progresso por janela. CSS desativa animações quando o sistema
solicita movimento reduzido; isso deve continuar respeitado.

Preservar mudanças preexistentes em AGENTS.md, briefing DOCX,
backend/reuniaoComAdvisorRaw.md e plano UI.

## Contrato do executor

- Escopo permitido: frontend/app/page.tsx, componente/hook dedicado à captura,
  frontend/lib/api.ts e capture-outcome.ts, estilos estritamente necessários,
  backend/app/api/main.py e schemas.py, backend/app/queue/jobs.py e worker.py
  se necessário para o comportamento da captura, e testes correspondentes.
- Usar a fila persistente existente. Cadastro e enfileiramento devem ser
  consistentes, normalizar OAB/UF e reutilizar captura ativa do mesmo escritório
  e OAB, inclusive em solicitações concorrentes. Preservar isolamento e auditoria.
- Mostrar cadastro/envio, aguardando execução, processamento, progresso
  confirmado, concluído, falha da fonte e perda de acompanhamento como estados
  distintos. Não inventar percentual, sucesso ou cancelamento no servidor.
- Permitir fechar modal durante processamento e reencontrar captura ao reabrir
  ou recarregar a página. Evitar prender outras ações ao estado global busy.
- Limitar chamadas de controle, incluindo getSession e leitura da resposta;
  falhas de rede devem liberar a interface, preservar o identificador do job e
  permitir consultar novamente sem criar duplicatas. Sucesso/falha da captura
  deve aparecer antes de um refresh secundário do dashboard.
- OAB cadastrada deve aparecer antes do término do trabalho. Sem worker ou
  sem progresso, mostrar demora e ação de reverificar; não spinner eterno sem
  explicação. Manter indicação textual útil com movimento reduzido.
- Testar sucesso com intimações/processos, zero resultados, DJEN 403/parcial,
  rede/sessão pendente, fechamento/reabertura, retomada, deduplicação e tenant.
- Não alterar prazos, protocolo, autos, fornecedores ou dados reais. Não fazer
  deploy ou commit pelo executor. Não delegar novamente.

## Verificações

- Backend: `.venv/Scripts/python.exe -m pytest` nos testes de captura/API/worker
  alterados e `.venv/Scripts/python.exe -m ruff check` nos arquivos alterados.
  Os testes devem usar banco isolado e provedores simulados.
- Frontend: `pnpm test`, `pnpm lint`, `pnpm typecheck`; build se viável no Windows.
- Coordenador: revisar diff real, verificar percurso no navegador com API
  simulada isolada, movimento normal/reduzido e viewport menor; investigar
  acesso DJEN somente por consulta limitada e sem afirmar validação de produção.

## Execução e revisão

Evidência nova coletada em 27/09, sem mutação de dados:

- Consulta DJEN limitada a um dia/página respondeu HTTP 200 em cerca de 1s.
- Saúde e OpenAPI da API de produção responderam 200, incluindo rotas de jobs.
- Transação READ ONLY no banco compartilhado encontrou captura com 601 novas
  intimações, 350 processos no banco e remoção do monitoramento nove segundos
  antes da captura terminar. O 403 de 22/09 não explica sozinho a tentativa atual.
- GitHub confirmou CI e deploy aprovados do commit anterior `cd96bbf`.
- Ferramenta de navegador informou zero browsers; criação de IAB e Chrome
  retornou indisponibilidade. Verificação visual real permanece indisponível.
- Sem Docker/PostgreSQL local identificado. Testes PostgreSQL devem passar no
  CI; nunca substituir o banco descartável pelo PostgreSQL compartilhado.

Revisão solicitou chave de idempotência persistida por conta para conciliar
resposta perdida mesmo após término do job; consultas auxiliares com timeout;
enriquecimento DataJud fora do resultado da captura; preservação do resultado
ao remover monitoramento; documentação do worker necessário em execução local.

Retomada em 28/09.

Implementação revisada: cadastro/enfileiramento atômicos com lock por escritório,
reuso de job ativo, replay de chave original e aliases, timeout de sessão e
resposta, recuperação por conta e descarte de respostas antigas. Cursor manual
só avança em sucesso com janela válida e monitoramento ainda ativo. Backfill
DataJud usa execução separada limitada a dois trabalhos, coalescida por escritório;
é best effort, sem fila persistente própria para retentativas.

Verificação local final: 105 testes frontend, lint, tipos e build Next aprovados.
Coordenador executou a suíte backend: 719 aprovados e 73 ignorados (inclui os
testes PostgreSQL sem banco local), Ruff completo aprovado. Também conferiu o
diff real e executou 24 testes de transporte, hook e tela. O teste DOM usa Home
real e cobre envio, fechar/reabrir sem novo POST e resultado antes de um refresh
pendente. PostgreSQL concorrente fica para CI isolado. Avisos: chave HMAC curta
nas fixtures existentes e navegação não implementada no jsdom.
Nenhuma captura real foi criada para testar a correção. Conferência visual no
navegador e validação da nova captura autenticada em produção permanecem pendentes.

O HTTP 403 observado em produção em 22/09 é histórico; não prova a resposta
atual nem sua causa.

CI 36493631376 aprovado (backend, frontend, PostgreSQL 16/17), deploy 36493774462
aprovado. O script confere imagem exata dos quatro serviços e /health. Consulta
externa confirmou /health 200 e request_id no esquema publicado. O fundador
confirmou captura de intimações/processos; READ ONLY de 29/09 encontrou job
concluído, 7/7 janelas e 13 intimações novas. Ausência de prazo é a separação
deliberada entre captura e revisão de contagem; UX dessa etapa no plano seguinte.
