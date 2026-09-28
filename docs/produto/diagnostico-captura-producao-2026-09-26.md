# Diagnóstico da captura por OAB em produção — 26/09/2026

## Atualização de 27/09: captura concluída com interface ainda aguardando

Nova consulta somente leitura ao banco compartilhado encontrou uma captura
concluída às 23h28min18s UTC de 27/09, com 601 intimações novas e sem erro DJEN
registrado. As contagens observadas eram 601 intimações e 350 processos.
Havia zero OAB monitorada: a auditoria registra remoção da OAB às 23h28min09s,
nove segundos antes do término da captura. A captura em andamento continuou
após a remoção. Não havia job de captura, pois a interface usa a rota síncrona.

Uma consulta direta limitada a um dia e uma página, feita desta máquina em
27/09, recebeu HTTP 200 do DJEN em aproximadamente um segundo, com 12
resultados na consulta e cinco itens retornados. Nenhum teor foi impresso ou
persistido nessa verificação. `/health` e `/openapi.json` da API de produção
também responderam HTTP 200; a API já expõe criação e consulta de jobs.
Essas observações não identificam a causa dos HTTP 403 históricos nem validam
a rede da VPS continuamente.

A revisão do frontend encontrou esperas sem timeout na sessão, na requisição
de captura e nas atualizações auxiliares. O estado ocupado só termina após
recarregar as OABs e todo o dashboard. Portanto, mesmo uma captura concluída
pode continuar aparecendo como em processamento se uma leitura posterior não
resolver. A correção em execução usa os jobs persistentes já existentes,
timeout de acompanhamento e resultado terminal independente do refresh.
O CSS também respeita `prefers-reduced-motion`: um ícone parado por essa
preferência não comprova interrupção da captura. A nova indicação de estado
precisa funcionar sem depender da animação.

## Evidência observada

Consulta **somente leitura** ao PostgreSQL compartilhado em 26/09:

- Não há OAB monitorada, intimação, processo ou job de captura atualmente no
  escritório cadastrado.
- Em 22/09, duas capturas manuais, de UFs distintas, registraram zero itens e
  `djen_indisponivel=true`. A primeira chamada ao DJEN retornou **HTTP 403**.
  O registro não contém corpo nem cabeçalhos da resposta; portanto não permite
  afirmar qual regra do CNJ bloqueou a origem.
- Em 22/09 houve remoção com limpeza que apagou 130 intimações, 130 prazos,
  75 processos e 6.614 andamentos. Outras remoções ocorreram em 22 e 23/09.
  Os eventos de auditoria foram preservados, mas não restauram os registros
  apagados. Será necessária uma nova captura depois de resolver a origem.

O código anterior devolvia HTTP 206 com zero resultados quando o DJEN falhava,
mas o frontend anunciava “Captura concluída”. A OAB era cadastrada antes da
consulta; o sucesso do cadastro não significava sucesso da captura. A captura
manual cria a intimação e um processo básico; o DataJud complementa metadados
depois. Ele não recupera autos completos. O motor não cria prazo definitivo sem
que a regra e o termo inicial sejam conferidos.

## Mudanças no checkout local

- A interface informa a falha/resultado parcial do DJEN, preserva a OAB
  cadastrada para nova tentativa e não exibe mais sucesso com zero itens quando
  a origem recusou a consulta. O aviso de 403 não expõe a URL com o número da
  OAB.
- “Parar monitoramento” usa remoção sem `purge`; intimações, processos e
  documentos já registrados permanecem.
- O cliente consulta 100 itens por página, valor documentado no Swagger atual
  do CNJ. Antes solicitava 50.
- Jobs de captura incompleta passam a `failed`, preservam dados parciais e não
  avançam o cursor. O comando `capture-due` retorna código 1 para alertar o
  operador. A janela inicial usa a data do cadastro para cobrir uma interrupção
  prolongada. Erros persistidos registram apenas classe/código, sem URL com OAB.

Essas correções só estarão ativas em produção após um deploy verificado. Testes
locais não removem o bloqueio HTTP 403 vindo da origem.

## Verificação necessária na VPS

1. Executar **uma** consulta GET de diagnóstico ao DJEN a partir do contêiner
   backend, com uma OAB de teste e janela curta. Registrar status, cabeçalhos
   `x-ratelimit-*`, eventual `retry-after`, corpo da resposta e IP de saída.
   Não registrar OAB real, token ou conteúdo de intimação em logs públicos.
2. Se o status continuar 403, comparar a mesma consulta em uma origem de rede
   brasileira autorizada e acionar o suporte do CNJ com os cabeçalhos e horário.
   O GET é documentado como público; a razão exata do 403 permanece aberta.
3. Confirmar se há cron externo chamando `python -m app.cli capture-due`. O
   `docker-compose.prod.yml` declara worker de jobs enfileirados, mas não um
   agendador periódico. Sem esse cron, OABs cadastradas só são capturadas pelo
   botão manual ou por job criado explicitamente.
4. Após resolver o acesso à origem e implantar as correções, cadastrar uma OAB
   autorizada, capturar uma janela conhecida, conferir contagem na resposta,
   intimações e processos no banco/tela, e observar dois ciclos agendados.

Referência oficial: [Swagger DJEN do CNJ](https://hcomunicaapi.cnj.jus.br/swagger/djen.yml),
versão 1.0.4. Ele documenta GET sem autenticação, controle por IP e valores 5
ou 100 para `itensPorPagina`; não esclarece a causa do 403 destas tentativas.
