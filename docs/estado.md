# Estado do Causor

Atualizado em 07/10/2026. Este arquivo descreve o estado **atual**. O registro
cronológico até 06/10 (com links de CI e deploy de cada entrega) está em
[`historico/estado-ate-2026-10-06.md`](historico/estado-ate-2026-10-06.md).

Níveis de evidência usados abaixo: **local** (testes na máquina), **CI**,
**implantado** (versão conferida na VPS), **validado em produção** (exercido
com dados reais) e **validado juridicamente** (revisado por advogado).

## Fluxo do MVP

Captura por OAB → prazo revisável → documentos do caso → contexto com fontes →
minuta → revisão humana. Protocolo judicial está fora do MVP.

| Etapa | O que existe | Evidência mais forte |
|---|---|---|
| Captura de publicações | DJEN por OAB, enriquecimento DataJud, agendador persistente (`capture-scheduler`, ciclo de 300s, intervalo por OAB). | Implantado. Captura real de 601 intimações em 27/09; agendador sem captura real observada após a migração do banco. |
| Prazos | Análise automática após cada captura: motor determinístico, catálogo CPC e prazo por tipo de ato; prazo calculado vale sem conferência; incerto recebe data de triagem (5 dias úteis; 2 no criminal); falha é repetida sozinha. Calendários locais não homologados. | Implantado em 07/10 (`c72e776`). Reanálise automática do acervo em produção ainda não conferida. Sem validação jurídica em casos reais. **Erro achado em 09/10:** teor HTML do DJEN quebrava a conferência literal e o prazo por tipo de ato substituía um prazo escrito diferente (caso real: 15 dias postos em vigor onde o teor dizia 5). Correção implantada em 09/10 (`4ca6e1e`, [CI](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37893816748) e [deploy](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37893998526)); nenhuma intimação real passou pela regra nova ainda ([plano](desenvolvimento/planos/2026-10-09-prazo-dias-escritos.md)). Avisos da Jev ("mais de um ato ou parte"), sem efeito sobre o prazo: ativos só com `CAUSOR_JEV_API_KEY` no `.env` da VPS ([plano](desenvolvimento/planos/2026-10-09-jev-no-produto.md)). |
| Avisos | E-mail por escritório: prazo novo e D-3/D-1/D-0/vencido, enviado pelo `capture-scheduler` entre 7h e 21h. WhatsApp fica para depois, como outro canal. | Implantado em 07/10 (`c72e776`), **inativo**: o envio pelo Resend ainda não funciona (relato do fundador, 07/10). Sem SMTP funcional nada é enviado. |
| Documentos | Upload manual por grau, SHA-256, validação de PDF, extração/OCR, resumos com citação literal (padrão Haiku ou aprofundado Sonnet). | Implantado. Percurso com PDFs fictícios. |
| Contexto e evidências | Trabalho jurídico com escopo declarado, índice de peças, busca nos originais, lacunas viram pendências, gate de contexto. | Implantado. Percurso sintético no navegador. |
| Minuta e revisão | Análise e redação em fila persistente e retomável; editor com proteção de texto; aprovação humana; PDF com timbrado. | Implantado. Sonnet 5.5 testado nas APIs reais com caso fictício. |
| Assistente | Consulta processos, intimações, prazos e trabalhos; abre trabalho. Não gera nem aprova minuta. | Implantado. |
| Equipe e papéis | Vários membros por escritório: administrador, advogado e assistente; convite pela aba Equipe; desativação sem apagar autoria; responsável em tarefa e trabalho, filtro "Minhas tarefas"; aviso de prazo para o responsável e os administradores. | Validado em produção em 07/10 (`63982b4`, [CI](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37714238559) com suíte Postgres e [deploy](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37714387087)); rotas `/equipe` conferidas por fora (401 sem sessão). Chave service-role e `CAUSOR_APP_URL` no `.env` da VPS; Site URL e Redirect URLs do Supabase corrigidas (o projeto novo de 06/10 tinha ficado em `localhost`). Convite real por e-mail testado pelo fundador em 07/10 e funcionando ([plano](desenvolvimento/planos/2026-10-07-equipe-e-papeis.md)). |

## Produção

- **Limpeza da VPS** (09/10): disco de 44 para 5,8 GB (93% → 13%). Apagadas
  100 imagens antigas do Causor (ficam a versão atual e a anterior) e removido
  o Evolution do Operly: containers, volumes, pasta e bloco no Caddy, com cópia
  do banco em `/root/backups`. O Evolution do infolex não foi tocado; infolex,
  app e API responderam 200 depois do reload do Caddy. **Pendente:** remover
  `/etc/cron.d/causor`, cron antigo de `capture-due` e `process-autos-due` que
  falha antes de rodar porque não consegue gravar o log. Para não encher de
  novo, o deploy passa a apagar as imagens antigas e o Compose limita o log de
  cada serviço a 30 MB (**local**, não enviado).
- **Resumo de autos longos** (`d3737bc`, 08/10): o perfil padrão passou de
  3000 para 6000 tokens de saída e, se a resposta ainda vier cortada, resume
  as metades. Causa: o PDF único de 22 páginas do caso fictício gerava resumo
  maior que o limite e falhava com `LLMProviderError`. CI e deploy aprovados;
  **validado em produção** no mesmo PDF (resumo completo, contexto e análise de
  evidências concluídos).
- **Incidente de 08/10:** um envio feito pelo backend local, cujo `.env` aponta
  para o banco de produção, criou o job com o armazenamento do PC
  (`local:b2d94ee5…`); o `autos-worker` da VPS nunca o pegou. Job 672 marcado
  como falho e PDF reenviado pelo app.causorai.com. Trocar o `.env` local para
  o Postgres local antes de voltar a usar o backend local.
- **Exclusão de cliente** (`f7ea2f2` e `47cbe06`, 09/10, **implantado**: a
  VPS roda `9750137`, que os inclui; exclusão real ainda não observada): botão "Excluir
  cliente" na ficha do cliente, para advogado e administrador
  (`DELETE /clientes/{id}`). Os processos do cliente ficam, sem parte
  representada, e as tarefas ficam sem o cliente; recusa se um processo dele
  tem minuta aprovada.
- **Exclusão de processo** (`8448520`, 09/10): botão "Excluir processo" na
  ficha do processo, para advogado e administrador
  (`DELETE /processos/{id}`). Apaga intimações, prazos, trabalhos, minutas em
  rascunho, tarefas, andamentos e documentos; recusa minuta aprovada e
  operação em andamento; arquivos no armazenamento e auditoria ficam. As
  publicações apagadas vão para `intimacao_descartada` (migração
  `d4b9e2f7a1c6`) e a captura não as recria; publicação nova do mesmo
  processo o traz de volta.
  [CI](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37890368879) e
  [deploy](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37890537113)
  aprovados; captura de OAB nova com prazos calculados observada pelo
  fundador depois do deploy. Exclusão real pelo app ainda não observada.
- **Exclusão de trabalho** (`b1a8b05`, 08/10): excluir trabalho (minuta em
  rascunho e pendências junto; recusa minuta aprovada e operação em
  andamento) e remoção do processo capturado que ficou sem trabalho, minuta,
  documento, tarefa, prazo confirmado e OAB monitorada. Processo cadastrado à
  mão fica. [CI](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37733098819)
  e [deploy](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37733268868)
  aprovados; conferidos por fora `/health` 200, app 200, `DELETE /trabalhos/{id}`
  sem sessão 401 e a rota no OpenAPI. Exclusão real na conta do fundador ainda
  não observada.
- **Equipe e papéis** (`63982b4`, 07/10).
  [CI](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37714238559) (inclui a suíte Postgres) e [deploy](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37714387087) aprovados; o
  deploy verifica o SHA nos cinco serviços. Convite por e-mail exercido pelo
  fundador.
- **Prazo automático** (`c72e776`, 07/10): prazo calculado após a captura.
  [CI](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37637027333) e [deploy](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37637262854) aprovados. Conferência externa: `/health` 200.
- **Reestruturação** (`b0fd16c`, 07/10): remoção do agente local e do
  protocolo.
  [CI](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37576541510) e
  [deploy](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37576706835)
  aprovados. Conferência externa: `/me` sem sessão 401, rotas de agente e
  conectores 404, OpenAPI sem rotas de protocolo, login do frontend 200.
- **Infra:** VPS Hostinger com Docker Compose (`backend`, `worker`,
  `autos-worker`, `capture-scheduler`, `frontend`), atrás do Caddy
  compartilhado. `app.causorai.com` e `api.causorai.com`.
- **Banco e Auth:** novo projeto Supabase Free desde 06/10, restaurado do
  anterior com usuários, senhas e auditoria preservados. O projeto antigo
  estourou o egress do plano Free (37 GB / 5 GB) em 30/09–01/10. As consultas
  foram corrigidas; o consumo mensal da versão nova ainda não foi medido.
- **Arquivos dos autos:** na VPS, API e `autos-worker` compartilham o volume
  `causor_artifacts`. No desenvolvimento local, o `localdev` grava no disco da
  máquina e a produção não enxerga esses arquivos. **Não enviar autos reais
  pelo backend local.**

## O que falta para o MVP funcionar de verdade

Critério de aceite: [aceite do primeiro caso](operacao/aceite-mvp-2026-10-08.md).

1. **Login com senha no navegador** do fundador no projeto Supabase novo. Até
   agora só foi verificado com sessão técnica.
2. **Captura real** com uma OAB autorizada em produção após a migração.
3. **Caso real autorizado**: processo, autos em PDF, cliente e polo, providência
   e advogado revisor. Ainda não definido. O advisor trará uma OAB.
4. **Minuta real revisada** com o registro de fontes, erros materiais e tempo
   ([ficha do caso](produto/marco-caso-real-2026-09-25.md)).

Um caso dá diagnóstico, não taxa de acerto. Depois de corrigir a primeira causa
material, repetir em cinco casos.

## Próximos passos

1. Fechar o aceite do primeiro caso real.
2. **Coleta automática dos autos:** comparar um fornecedor (Judit, Escavador ou
   alternativa) com o inventário manual do mesmo caso — cobertura por
   documento, faltas, custo, atraso e intervenção. Só então integrar.
3. **Prazo automático** (implantado em 07/10, `c72e776`): fazer o envio pelo
   Resend funcionar no SMTP da VPS (`CAUSOR_SMTP_HOST`, `CAUSOR_SMTP_USER`,
   `CAUSOR_SMTP_FROM`, `CAUSOR_SMTP_PASSWORD`) e conferir na conta de teste que a reanálise
   automática converteu as intimações da versão anterior
   ([plano](desenvolvimento/planos/2026-10-07-prazo-automatico.md),
   [operação](operacao/captura-periodica.md)). Custo estimado da reanálise:
   cerca de US$ 0,005 por intimação (Haiku), uma vez.
4. Interface: reformulação "Papel e tinta" **implantada** em 07/10
   (`0db2b1b`, [CI](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37585288275)
   e deploy verdes): um sistema visual só, com Satoshi nos títulos e Inter na
   interface, fundo papel e tinta preta (o verde de acento saiu em 08/10: a marca
   é preta, grafite e cinza), tabelas com colunas alinhadas e
   selos em frase normal. Aprovada pelo fundador no ambiente local; em
   produção, conferidos `/health` 200, `/me` sem sessão 401, app 200 e as
   fontes novas servidas. Plano em
   [`desenvolvimento/planos/2026-10-07-reformulacao-ui.md`](desenvolvimento/planos/2026-10-07-reformulacao-ui.md).
   Em 09/10, para acompanhar a landing nova (referência harvey.ai), os títulos
   de 20px para cima passaram de Satoshi para Newsreader (números seguem em
   Inter), a barra lateral ficou em tinta nos dois temas e o login e a definição
   de senha ganharam o painel pintado da landing ao lado do formulário
   (`components/AuthShell.tsx`). Verificado localmente com a seed
   de demonstração (`pnpm check` e `pnpm build`); implantado em 09/10
   (`a120a76`, incluído na versão `9750137` que a VPS roda).

## Fora do escopo agora

- **Protocolo automático e agente local:** removidos do código em 06/10. As
  tabelas do banco foram mantidas, sem migração.
- **MNI:** o leitor no servidor continua no código, sem interface. Depende de
  credenciamento que pode não ser concedido a CNPJ privado
  ([histórico](historico/trilhas-adiadas/mni-credenciamento.md)).
- Automação específica de PJe, e-SAJ, eproc ou Projudi.
