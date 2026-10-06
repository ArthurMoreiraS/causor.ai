# Captura periódica de OAB

O serviço `capture-scheduler` usa a mesma imagem/versionamento do backend.
A cada 300 segundos consulta os cadastros ativos e enfileira apenas os devidos.
O worker existente executa os jobs; o agendador não consulta o DJEN nem chama LLM.
O intervalo entre capturas bem-sucedidas é o `intervalo_horas` da OAB (padrão 12).

Primeira janela automática: dia brasileiro menos `capture_lookback_days` (3),
até o dia brasileiro atual. Para histórico anterior, usar a captura manual com
janela explícita. Após sucesso, próxima janela parte do cursor menos a
sobreposição. Falhas preservam o início anterior e não avançam o cursor.
Há uma espera de 900 segundos após falha antes de enfileirar nova tentativa.
Jobs ativos impedem outra captura automática ou manual da mesma OAB/tenant.

Configuração opcional na `.env` do servidor:

```dotenv
CAUSOR_CAPTURE_SCHEDULER_TICK_SECONDS=300
CAUSOR_CAPTURE_FAILURE_COOLDOWN_SECONDS=900
```

Valores devem ser positivos. A leitura da lista de OABs e do último job é
limitada; não são lidos textos/payloads de todo o acervo no agendador.

## Conferência operacional

```bash
docker compose --env-file .env --env-file .image_tag.env ps capture-scheduler worker
docker compose --env-file .env --env-file .image_tag.env logs --tail 30 capture-scheduler
docker compose --env-file .env --env-file .image_tag.env exec capture-scheduler python -m app.capture.service --healthcheck
```

A saúde exige um ciclo inteiro concluído recentemente, inclusive quando não
há OAB devida. Falhas de banco repetidas deixam o serviço unhealthy. Esse estado
é detectável, mas `restart: unless-stopped` não reinicia automaticamente um
container apenas por estar unhealthy. SIGTERM encerra a espera entre ciclos.
O deploy valida saúde e SHA do serviço junto aos demais containers.

Não operar um cron/Agendador de Tarefas chamando o antigo `capture-due` em paralelo
com este serviço. O comando legado continua síncrono; sua retentativa interna
não é o mecanismo usado pelo serviço persistente. Remover esse cron externo,
caso exista, antes de habilitar o serviço.

Uma instalação saudável não comprova cobertura real de publicações. Conferir
uma OAB autorizada, job concluído, cursor e publicação conhecida. Prazos gerados
continuam calculados a revisar; fontes indisponíveis e exceções exigem conferência.
