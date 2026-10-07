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
| Prazos | Análise automática após cada captura: motor determinístico, catálogo CPC e prazo por tipo de ato; prazo calculado vale sem conferência; incerto recebe data de triagem (5 dias úteis; 2 no criminal); falha é repetida sozinha. Calendários locais não homologados. | Catálogo por ato implantado. Triagem, reanálise automática e "cumprir sem confirmar" só **local** (07/10). Sem validação jurídica em casos reais. |
| Avisos | E-mail por escritório: prazo novo e D-3/D-1/D-0/vencido, enviado pelo `capture-scheduler` entre 7h e 21h. WhatsApp fica para depois, como outro canal. | **Local** (07/10). Em produção falta configurar SMTP; até aqui nenhum aviso saía porque o comando não era agendado. |
| Documentos | Upload manual por grau, SHA-256, validação de PDF, extração/OCR, resumos com citação literal (padrão Haiku ou aprofundado Sonnet). | Implantado. Percurso com PDFs fictícios. |
| Contexto e evidências | Trabalho jurídico com escopo declarado, índice de peças, busca nos originais, lacunas viram pendências, gate de contexto. | Implantado. Percurso sintético no navegador. |
| Minuta e revisão | Análise e redação em fila persistente e retomável; editor com proteção de texto; aprovação humana; PDF com timbrado. | Implantado. Sonnet 5.5 testado nas APIs reais com caso fictício. |
| Assistente | Consulta processos, intimações, prazos e trabalhos; abre trabalho. Não gera nem aprova minuta. | Implantado. |

## Produção

- **Versão implantada:** `b0fd16c` (07/10): reestruturação com remoção do
  agente local e do protocolo.
  [CI](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37576541510) e
  [deploy](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37576706835)
  aprovados; o deploy verifica o SHA nos cinco serviços. Conferência externa:
  `/health` 200, `/me` sem sessão 401, rotas de agente e conectores 404,
  OpenAPI sem rotas de protocolo, login do frontend 200.
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
3. **Prazo automático** (07/10, **local**): publicar e configurar o SMTP na
   VPS ([plano](desenvolvimento/planos/2026-10-07-prazo-automatico.md),
   [operação](operacao/captura-periodica.md)). Na primeira execução, o
   agendador reanalisa em lotes de 100 por ciclo as intimações da versão
   anterior (custo de chamadas ao Haiku).
4. Interface: reformulação "Papel e tinta" **implantada** em 07/10
   (`0db2b1b`, [CI](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/37585288275)
   e deploy verdes): um sistema visual só, com Satoshi nos títulos e Inter na
   interface, fundo papel e verde da landing, tabelas com colunas alinhadas e
   selos em frase normal. Aprovada pelo fundador no ambiente local; em
   produção, conferidos `/health` 200, `/me` sem sessão 401, app 200 e as
   fontes novas servidas. Plano em
   [`desenvolvimento/planos/2026-10-07-reformulacao-ui.md`](desenvolvimento/planos/2026-10-07-reformulacao-ui.md).

## Fora do escopo agora

- **Protocolo automático e agente local:** removidos do código em 06/10. As
  tabelas do banco foram mantidas, sem migração.
- **MNI:** o leitor no servidor continua no código, sem interface. Depende de
  credenciamento que pode não ser concedido a CNPJ privado
  ([histórico](historico/trilhas-adiadas/mni-credenciamento.md)).
- Automação específica de PJe, e-SAJ, eproc ou Projudi.
