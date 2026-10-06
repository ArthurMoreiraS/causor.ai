# Reduzir tráfego de saída do Supabase

Estado: correção local validada; implantação e liberação da organização pendentes.

Preferência confirmada pelo fundador em 05/10: continuar no Supabase Free.
Não contratar upgrade nem adicionais. Estratégia: publicar as otimizações,
manter consumo futuro dentro dos 5 GB e acompanhar o uso após retomada.
A restrição atual só tem liberação automática gratuita na renovação indicada
em 22/10. O fundador confirmou o envio do pedido de exceção ao suporte em
05/10; resposta e liberação ainda não confirmadas. Não usar criação/transferência
de projetos para contornar cota.
Ainda não há medição que prove o consumo mensal da versão corrigida.

## Contexto e evidência

Fundador pediu resolver os avisos Supabase: 37,27 GB / 5,5 GB, serviços
restritos, renovação indicada no email em 22/10/2026. Não há navegador
conectado nesta sessão. Print do painel recebido: 37,39 GB / 5 GB,
cached egress zero, pico próximo de 28 GB em 30/09 e outro em 01/10.
O print não mostra a distribuição por serviço.
Documentação oficial confirma liberação imediata com Pro, a partir de
US$ 25/mês, 250 GB de egress; contratação não autorizada nesta tarefa.

Consulta READ ONLY em 05/10: conexão ao pooler funciona; estatísticas
acumuladas desde 23/07. Consulta ordenada de intimações retornou 887.692
linhas em 1.621 chamadas; consulta sem ordem/limite retornou 445.805 em
821 chamadas. Ambas selecionam teor e payload completos. Há zero
intimações atualmente, portanto não é possível estimar o tamanho histórico.
Estatísticas acumuladas não provam a atribuição dos 37,27 GB do ciclo.

Código: dashboard operacional carrega todas as entidades para contar;
loadDashboard carrega sete endpoints e duplica leituras de intimações;
Home recarrega tudo a cada 5 s enquanto existe prazo em análise.

## Escopo de implementação

Execução direta nesta sessão. Não implantar, contratar, alterar
dados reais, ler/imprimir segredos ou executar suites contra banco real.

Escopo permitido: backend/app/api/main.py, schemas.py e helper de leitura
novo em api se necessário; frontend/app/page.tsx, frontend/lib/api.ts,
helper/hook de acompanhamento novo; testes específicos backend/frontend.
Preservar mudanças preexistentes em docs/estado.md, plano de
01/10 e todos os arquivos não rastreados. Em 05/10 o fundador solicitou
remover o fluxo obrigatório de delegação Astra/Sol: regra retirada de
AGENTS.md, guia fluxo-codex.md removido e referências de desenvolvimento
limpas nos planos. Não altera modelos nem workers usados pelo produto.

Objetivos:

- Calcular métricas no SQL, sem transferir entidades/textos ao backend
  apenas para contar. Preservar semântica de prazos confirmados e a revisar,
  risco, atrasados, minutas e isolamento por escritório.
- Listagens /intimacoes e /review/queue não devem transferir o payload
  original DJEN do banco. Projetar apenas campos da resposta e memória de
  prazo necessária, preservando teor e contrato HTTP. Não modificar instâncias
  ORM com payload parcial nem causar lazy load/N+1 do payload original.
- Acompanhamento de prazo consulta endpoint compacto com ID e memória/estado
  necessário, sem teor nem payload original e com isolamento por escritório.
  Não recarrega sete endpoints repetidamente. Atualiza badges durante a análise
  e faz refresh completo ao término; mantém ações e retries atuais.
  Evita chamadas sobrepostas e polling enquanto aba oculta; retoma visível.
- Preservar navegação informativa, conteúdo jurídico, auditoria, revisão humana,
  cálculo determinístico e contratos de captura/trabalhos existentes.

## Aceite e verificações

Testes com dados sintéticos/SQLite: métricas corretas entre escritórios e
estados de prazo; SQL dos endpoints não seleciona payload original inteiro
ou entidades para contagem; listagem mantém teor e memória do prazo;
endpoint compacto sem teor/payload bruto; frontend consulta status compacto,
encerra polling/refresh terminal, não sobrepõe pedidos e pausa invisível.
Não alterar testes apenas para espelhar a implementação.

Backend: ./.venv/Scripts/python.exe -m pytest -q nos testes modificados
e regressões API/pipeline pertinentes; ./.venv/Scripts/python.exe -m ruff
check nos arquivos modificados. Frontend: pnpm.cmd check.
git diff --check. Venv exige sandbox escalation para acessar Python instalado;
usar aprovação normal da sessão se necessário, nunca expor credenciais.

Revisar arquivos, resultados, riscos e limitações, inspecionar
diff e executar verificações relevantes. Resultado local não significa deploy
nem desbloqueio do Supabase. Próximo passo operacional depende de painel
e opção de contratação ou espera do fundador.

## Resultado e limites

- Métricas usam agregações SQL; não carregam textos jurídicos para contar.
- Intimações/fila projetam o teor e apenas a memória de prazo do JSON;
  preservam contrato de resposta e payload original no banco. Prazos e resumo
  de processos também usam projeções sem payload original e sem lazy loads.
- Endpoint GET /intimacoes/analise-status recebe até 200 IDs por chamada,
  com filtro de escritório; frontend divide lotes maiores. Polling serial
  atualiza estados intermediários e recarrega o dashboard ao término.
  Pausa em aba oculta; ignora respostas de conta/job anterior e concilia
  retry feito em outra aba. Remoção de registros e falhas transitórias cobertas.
- Badge de cálculo provisório continua explícito mesmo antes do refresh final.
- Backend: 37 testes direcionados aprovados (55 deselecionados), Ruff completo
  aprovado. Comando: pytest -q tests/test_read_egress.py
  tests/test_tenant_isolation.py tests/test_djen_deadline_pipeline.py
  tests/test_api.py -k 'read_egress or tenant or djen or dashboard or
  processos_resumo or listar_intimacoes or listar_prazos or fila_revisao or health'.
  Execução mais ampla de test_api.py foi interrompida após demora prolongada
  em caminhos não relacionados; não há resultado completo dessa execução.
- Frontend pnpm.cmd check: lint, tipos e 160 testes aprovados, incluindo
  integração Home/badges/refresh terminal. Sem teste visual em navegador.
- Novos reusos PostgreSQL ficam em tests/postgres/test_postgres_read_egress.py
  para CI descartável; não executados localmente. As três verificações iniciais
  foram ignoradas por ausência do banco descartável antes de acrescentar os
  quatro casos de borda. Consulta READ ONLY com as novas projeções/agregações
  no PostgreSQL real passou, com contagens zero; não valida casos preenchidos.
- Verificação externa: Auth Supabase /auth/v1/settings respondeu 402;
  https://api.causorai.com/health respondeu 200. Não houve contratação,
  implantação, migração ou alteração de dados reais.
- Supabase documenta que quota consumida permanece até renovação; excluir
  dados/projetos não devolve egress. Para desbloqueio imediato, Free → Pro;
  sem upgrade, email indica renovação em 22/10/2026. Custo começa em
  US$ 25/mês, sujeito a quantidade/configuração dos projetos e adicionais.
  Liberação do serviço e redução efetiva em produção ainda não verificadas.

## Fontes oficiais

- https://supabase.com/docs/guides/platform/manage-your-usage/egress
- https://supabase.com/docs/guides/platform/billing-faq
- https://supabase.com/pricing
