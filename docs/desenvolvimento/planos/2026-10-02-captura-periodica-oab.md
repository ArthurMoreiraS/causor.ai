# Captura periódica por OAB

Continuação autorizada pelo fundador em 02/10, após publicação da análise e
minuta recuperáveis (`edf41d1`). Coordenador conferiu `docs/estado.md`, diff e
implementação atual: `capture-due` existe como execução síncrona, mas Compose
de produção não tem agendador. Worker consome fila, não cria ciclos periódicos.
Não prometer coleta de autos inteiros ou qualidade jurídica por este avanço.

## Objetivo e escopo

Implementar um serviço persistente de
agendamento que enfileira capturas de OABs ativas na fila já existente. Não faz
HTTP/modelo na transação do agendador. Datas da janela usam o dia brasileiro;
cursor e sobreposição preservam dias ainda não capturados após indisponibilidade.
O worker existente executa e inicia análise de prazo pelo pipeline atual.

Arquivos permitidos: capture/scheduler.py e novo módulo capture de serviço,
queue/jobs.py apenas validação de OAB agendada e avanço de cursor, settings.py,
CLI se necessário ao entry point; infra/docker-compose.prod.yml, infra/deploy.sh,
testes scheduler/serviço/captura/deploy/PG diretamente relacionados. API/main.py
somente se a concorrência com cadastro/remoção/captura manual exigir mesma ordem
de locks, com justificativa. Sem mudanças de frontend, calendário, classificação,
autos, trabalho/minuta, protocolo, integração de tribunal ou fornecedor.
Retomada em 06/10: execução direta, conforme instrução do fundador para retirar
o fluxo de delegação entre modelos. Critérios abaixo continuam válidos.

## Critérios de aceite

- Cada ciclo seleciona apenas OAB ativa e vencida ou nunca capturada. Enfileira
  job persistente audível pelo tenant, sem executar rede no agendador. Respeita
  intervalo da OAB após sucesso e espera configurável após falha (evitar loop
  que sobrecarrega DJEN). Não consulta histórico inteiro por omitir janela.
- Cadastro ativo existente é revalidado sob locks. Dois agendadores e pedido
  manual concorrente não criam capturas ativas duplicadas da mesma OAB/tenant.
  Usar ordem coerente de locks com captura manual e remoção (escritório primeiro
  na criação); consulta não deve misturar escritórios ou OABs com IDs coincidentes.
- Job agendado persiste antes de execução; reinício não duplica ativo. Falha e
  captura parcial não avançam cursor/última conclusão. Sucesso atualiza cursor
  monotonamente e timestamp de conclusão, preservando fluxo manual/legado.
  Cadastro removido/inativo antes de executar não captura nem é ressuscitado.
- O loop sobrevive a falha transitória de banco; log não imprime segredos nem
  teor de comunicações. Espera/tick configurável positivo. Healthcheck confere
  tick recente concluído, inclusive sem OABs; falha persistente fica unhealthy.
  Implementar parada apropriada para SIGTERM e testes sem sleeps reais.
- Compose declara capture-scheduler com imagem do backend, reinício e healthcheck.
  Deploy confere imagem/SHA do novo serviço e não declara sucesso se ele faltar
  ou estiver com versão antiga. Não criar cron externo adicional. O entry point
  capture-due legado continua compatível; documentar evitar operação paralela de
  cron legado com serviço novo ou alinhar a mesma deduplicação se necessário.

## Verificação e publicação

TDD para seleção/intervalo/falha/reinício/inatividade, datas/tenant/duplicação,
conclusão e cursor, loop/health e deploy com Docker/curl falsos. Integração fake
agendamento → worker → comunicação → análise de prazo sem navegador. Duas sessões
PostgreSQL descartáveis para agendadores concorrentes e manual versus automático.
Executar pytest dirigido, Ruff e suíte backend; CI completo com PostgreSQL 16/17.
Não usar banco real, provedor real ou PDF real como teste. Sem biblioteca/API nova
nem mudança de parâmetros DJEN. Revisar diff e testes pertinentes,
aplicar correções, publicar conforme autorização existente e conferir CI/deploy/SHA
e saúde. Deploy que instala serviço comprova disponibilidade, não acerto jurídico
ou cobertura real de publicações; execução real requer observação de uma OAB
cadastrada pelo fundador, sem fabricar dados na conta.

Preservar AGENTS.md e arquivos não rastreados do fundador. Atualizações locais de
estado e plano anterior registram deploy já concluído e podem entrar no próximo
commit com o novo trabalho.

## Execução em 06/10

Implementação direta concluída localmente, com critérios de cursor/retentativa,
cancelamento e deduplicação cobertos por testes. `remover_oab_monitorada` agora
trava escritório antes de selecionar registros/jobs, serializando com enfileiramento.
Rechecagem do job também antes de concluir a última janela evita publicar depois
de remoção/interrupção. Nunca reexecutar job agendado já encerrado.
Primeira janela automática é limitada a lookback; falha conserva início do job,
em vez de deslizar a janela durante indisponibilidade anterior ao primeiro sucesso.

54 testes direcionados e Ruff aprovados. Suíte completa: 803 aprovados e 108
ignorados em SQLite/sem credenciais externas. Quatro testes PostgreSQL aguardam
CI descartável, incluindo dois agendadores contra solicitação manual e remoção
concorrente. Serviço declarado no Compose; deploy verifica SHA também do
capture-scheduler e aguarda saúde. Sem implantação ou captura real nesta etapa.
[Operação](../../operacao/captura-periodica.md).
