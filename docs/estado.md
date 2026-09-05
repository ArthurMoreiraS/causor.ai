# Proximos passos - MVP

> **05/09 — correção de remoção de OAB implantada (`ad9bfb6`).** Erro 500 reproduzido
> com FKs ativas; limpeza passou a excluir os dependentes dos autos/contexto
> e notificações antes do processo/prazo. Jobs limitados ao escritório correto.
> Clientes, tarefas e auditoria preservados. Sem mudança de esquema ou remoção
> de OAB real nesta execução. Veja o [registro da correção](produto/correcao-remocao-oab-2026-09-05.md).
> CI aprovado: **676 backend, 42 em cada PostgreSQL (16/17), 75 frontend**,
> lint, tipos e build. Quatro serviços saudáveis e versão exata conferida na
> VPS em 05/09 às 01h53 (Brasília).
> [Deploy](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/33945546116).

> **05/09 — escritório integrado: primeira expansão implantada (`c0e18fb`).** A visão
> autorizada agora inclui atendimento, agenda, documentos, honorários e portal,
> em entregas sucessivas ligadas ao mesmo cliente/caso. A primeira entrega
> adiciona Clientes e Tarefas persistentes, associações com processo/intimação/
> alerta da minuta, responsável, data interna, controle de versão e auditoria.
> A sidebar foi ampliada e organizada por rotina; minutas `em_revisao` voltam
> à fila de aprovação. Não há navegador disponível para validação visual.
> CI aprovado: **670 testes gerais backend, 36 em cada PostgreSQL (16/17),
> 75 frontend**, lint, tipos e build Linux. Migração `a6c2e8f4b0d3` aplicada;
> imagens e saúde dos quatro serviços verificadas em 05/09 às 01h21 (Brasília).
> [Deploy](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/33944092928).
> Veja o [mapa de módulos e ordem de execução](produto/escritorio-integrado-2026-09-05.md).
> O próximo bloco continua sendo a revisão dos cinco casos pelo advogado;
> exemplos reais e homologação de tribunal permanecem pendentes.

> **05/09 — checkpoints e revisão cega implantados (`1466537`).** OCR/IA rodam
> sem transações abertas; extração/resumo concluídos sobrevivem à interrupção,
> e resultados de workers sem posse vigente são descartados. Há comando local
> para preparar minutas e ficha de revisão sem metadados do modelo.
> CI: **658 testes gerais backend, 22 em cada PostgreSQL (16/17), 70 frontend**,
> lint, tipos e build aprovados. Migração `a5f1b7d3c9e2`, imagens dos quatro
> serviços e API verificadas na VPS em 05/09 às 00h22 (Brasília).
> [Deploy](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/33941434207).
> O fundador confirmou um advogado revisor. Próximo foco: avaliar cinco casos
> e melhorar as evidências conforme os erros encontrados. Veja o
> [roteiro do piloto](produto/piloto-cinco-casos-2026-09-05.md) e o
> [registro técnico](produto/execucao-2026-09-04.md). Qualidade jurídica real e
> protocolo automatizado permanecem sem validação; casos e acesso ao tribunal
> ainda precisam ser disponibilizados.

> **04/09/2026 — Postgres, recuperação e auditoria implantados (`12b5709`).** A etapa
> adiciona CI com Postgres 16/17 e migrações reais; proteção de `audit_log`
> contra UPDATE/DELETE/TRUNCATE; preservação de eventos na limpeza de OAB/demo;
> retomada auditada de jobs documentais legados, sem tomar jobs bloqueados.
> Protocolo judicial fica fora da recuperação por tempo. CI aprovado: **640
> testes gerais backend, 14 cenários em cada Postgres (16/17), 70 frontend**,
> lint e build. Migração `a4d9e2c7b6f1` aplicada e quatro serviços verificados
> na VPS. [Deploy](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/33937823777).
> Limites: OCR/LLM ainda mantêm uma transação; administradores do banco podem
> alterar DDL. Próximo bloco: leases/checkpoints, transações curtas e rejeição
> de resultados de workers que perderam a posse. Veja o [registro](produto/execucao-2026-09-04.md).

> **04/09/2026 — continuação com push autorizado.** `bb75395` está na `main`;
> CI/Linux aprovado, incluindo o build de produção. O deploy antigo deu falso
> sucesso: download das imagens recusado pelo registro, seguido de `/health`
> da versão anterior. O script corrigido autentica com token temporário, para
> em falhas, sincroniza o Compose e confere as imagens dos quatro serviços.
> **Implantação confirmada de `69ac8cb`:** login no registro bem-sucedido,
> quatro serviços iniciados, imagens conferidas e API saudável. O worker de
> autos foi criado na VPS. [Logs do deploy](https://github.com/ArthurMoreiraS/causor.ai/actions/runs/33932711859).
>
> Redação com inventário/resumos preservados, seleção lexical de excertos,
> limites explícitos e fontes enviadas registradas no dossiê. Divergência entre
> prazo da IA e prazo cadastrado fica sinalizada; redação usa o cadastrado.
> Validação no CI/Linux: **635 testes backend, 6 pulados; 70 frontend**,
> lint, tipos e build de produção aprovados.
> Próxima etapa interna: Postgres/recuperação e auditoria. Veja os limites e
> configurações no [registro de execução](produto/execucao-2026-09-04.md).

> **04/09/2026 — execução autorizada e implementada localmente.** O fluxo por
> upload agora liga extração, resumos citados, contexto e minuta. O painel e o
> gate consultam a prontidão real. Há seleção de grau, declaração justificada de
> ausência e retomada de documentos legados. A captura deixou de fabricar prazos
> de 15 dias; prazo incerto fica pendente e pode ser confirmado com auditoria.
> Aprovação usa PDF persistido por hash; edição invalida aprovação. Registro
> manual distingue ausência/referência de comprovante e identifica o declarante.
> Console não marca alertas como entregues. Adapter Astra e harness de avaliação
> estão disponíveis por configuração de tarefa.
>
> **Validação final:** 620 testes de backend passaram, 6 foram pulados; 69 testes
> de frontend passaram, com ESLint e TypeScript. Ruff e `git diff --check` passaram.
> O teste HTTP ponta a ponta usa provedores simulados. O build compilou e gerou
> as páginas com valores fictícios de Supabase do CI; a montagem `standalone`
> foi bloqueada por permissões de symlink do Windows. Não houve deploy nem
> avaliação paga de modelo. Banco de testes: SQLite, sem homologação Postgres.
>
> O fundador confirmou desenvolvimento solo e ausência de acesso a qualquer
> tribunal. Leitura/protocolo pelo agente local seguem sem handlers operacionais.
> Leia o [registro de execução e operação](produto/execucao-2026-09-04.md), o
> [plano de evolução](produto/plano-evolucao-2026-09-04.md), a
> [pesquisa](areas/pesquisa-mercado-2026-09-04.md) e o
> [diagnóstico anterior à implementação](areas/diagnostico-causor-2026-09-04.md).
> Os registros datados abaixo não substituem este estado corrente.

> **2026-08-01 — o que executar agora está em
> [`superpowers/plans/2026-08-01-execucao-imediata.md`](superpowers/plans/2026-08-01-execucao-imediata.md)**,
> que detalha as duas semanas seguintes do plano de 90 dias a partir da
> [`areas/analise-competitiva-2026-08-01.md`](areas/analise-competitiva-2026-08-01.md).
> Aquela pesquisa confirmou a rota de 29-30/07 (Enter virou unicornio de US$ 1,2 bi
> sem construir a camada de dados e sem protocolar; Eve e EvenUp idem) e trouxe um
> fato que reprecifica a venda: o **Jus IA do Jusbrasil passou a ser gratuito em
> todos os planos** (13/04/2026, 300 mil advogados/mes). Redacao assistida virou
> item de plano basico; o diferencial que sobra e o que esta embaixo dela.

## Onde estamos

- **2026-07-31 — Upload dos autos pelo advogado.** `POST
  /processos/{id}/autos/upload` (multipart) + botao "Enviar os autos" no painel
  de Autos. Reusa as quatro etapas do agente (`open_capture` com
  `fonte="upload"` → `record_initial_manifest` → `confirm_document_upload` →
  `finalize_capture`), entao hash recomputado, magic bytes, versao imutavel e
  extracao enfileirada valem igual. **Unico caminho de captura sem gate
  externo.** A completude e registrada como *declarada pelo advogado* em
  `evidence` — no upload as duas enumeracoes sao a mesma lista que o advogado
  entregou, e isso nao pode ser vendido como a prova que a captura de tribunal
  da. Ver `autos/upload.py`.

  **2026-08-01 — a declaracao passou a ser confrontada.** `autos/conferencia.py`
  consulta o DataJud e compara os movimentos de juntada do tribunal com os
  arquivos recebidos; o resultado fica em `evidence.conferencia_datajud` e sai
  na resposta do upload (`CapturaOut.conferencia_datajud`). **Continua sendo
  sinal, nao prova**: movimento processual nao e peca dos autos, entao
  divergencia serve para perguntar ao advogado se faltou peca, nunca para
  reprovar a captura. Falha ou indisponibilidade do DataJud e engolida (uma
  tentativa so, via `get_datajud_client`), porque a captura ja esta completa
  quando a conferencia roda.

  **Contexto que mudou no mesmo dia:** o acesso ao advogado-advisor acabou (sem
  credencial de eproc, sem processos ativos). As Tasks 6-9 saem do roadmap por
  falta de acesso, nao por prioridade, e o gargalo do projeto passa a ser
  **falta de usuario**, nao falta de tribunal. Plano revisado em
  [`areas/plano-90-dias-2026-07-30.md`](areas/plano-90-dias-2026-07-30.md).

- **2026-07-21/22 — Canal oficial MNI: leitura implementada, endpoints
  verificados.** Cliente SOAP no backend, credencial por tribunal no vault,
  captura roteada por `CapturaAutos.fonte` ("mni" | "agente") pelo mesmo
  pipeline de integridade do Plano 2, UI em Configuracoes → Acesso aos
  tribunais. O assistente JIT deixou de pedir pareamento/login quando a rota
  tem credencial MNI — era a unica repeticao entre os dois fluxos.

  Varredura de 2026-07-22 sobre 303 URLs candidatas: 16 responderam,
  consolidadas em **14 perfis `(tribunal, grau)`** em 9 tribunais, todos MNI
  2.2.2 com `consultarProcesso` e `entregarManifestacaoProcessual`. A lista
  vive so em [`areas/mni-credenciamento.md`](areas/mni-credenciamento.md) e no
  codigo (`connectors/mni/profiles.py`). A tabela de perfis
  passou a aceitar **so endpoint confirmado**: falha de MNI marca a captura
  `failed` e nao cai para o agente, entao perfil palpitado mandava o advogado
  para um erro em vez do caminho que funciona. Sairam TJMG/TJDFT/TJBA e os 24
  TRTs (padrao registrado estava errado — 404).

  Autenticacao confirmada como usuario/senha no schema real
  (`idConsultante`/`senhaConsultante`), batendo com o que o `MniClient` ja
  enviava. Endpoints, ressalvas e o checklist do oficio:
  [`areas/mni-credenciamento.md`](areas/mni-credenciamento.md).

  **CORRIGIDO EM 2026-07-29 — o credenciamento nao e "bloqueio unico", e uma
  aposta nao verificada.** A pesquisa de mercado
  ([`areas/viabilidade-mercado-2026-07-29.md`](areas/viabilidade-mercado-2026-07-29.md) §2)
  mostrou que o MNI e desenhado para orgao publico: o Termo de Adesao do STF
  restringe a orgaos do art. 246 §2 do CPC, o TRF6 exige matricula funcional e
  delegacao formal de competencia, o webservice do eproc e descrito como
  autorizado so a orgaos do Judiciario, e o CNJ atende o advogado por outro
  caminho (Escritorio Digital, CNJ + OAB, gratuito). Pode ser um "nao"
  estrutural, nao uma fila burocratica. **Testar por escrito antes de investir
  mais** (checklist na secao 0 de
  [`areas/mni-credenciamento.md`](areas/mni-credenciamento.md)).
  Independente disso: WSDL acessivel nao e servico funcional.

- **2026-07-10 — Plano 2 (autos integrais e contexto citado): COMPLETO
  (Tasks 1–10)** (branch `feat/autos-contexto-integral`):
  - Captura integral com prova de completude: enumeracao inicial/final com
    fingerprint SHA-256, versoes imutaveis por hash, HTML disfarcado de PDF
    rejeitado por magic bytes; `complete` so com enumeracoes identicas e todo
    item verificado.
  - Extracao de texto por pagina com OCR (Tesseract `por`) apenas em pagina
    sem camada textual; worker persistente `process-autos-due` fora do request.
  - Trechos citaveis (chunks por pagina) com busca lexical (FTS portugues no
    Postgres; migracao `c8e6f0a4b3d2`).
  - Resumo estruturado por documento com citacoes verificadas contra os
    chunks — quote inventado marca o resumo `failed`.
  - `ContextoProcesso` ready exige 1o e 2o grau completos (ou not_applicable
    com evidencia) + 100% dos arquivos extraidos e resumidos; o drafter passa
    a receber inventario + excertos citados com rotulos [DOC-N p.M].
  - **Gate fail-closed**: minuta e protocolo bloqueiam (HTTP 409) sem contexto
    ready/atual; override do advogado e de uso unico, expira em 30 min, exige
    justificativa 20–1000 chars e gera auditoria.
  - UI: painel "Autos" por processo (captura, contagens, motivo do bloqueio,
    liberacao excepcional com aviso).
  - Download privado por ticket assinado de 300s (auditado, URL nunca
    persistida; localdev usa rota autenticada da API) e descarte explicito:
    `purge_process_objects` apaga em lotes de 100 com hashes na auditoria;
    sem expiracao automatica por idade. Chaves de objeto imutaveis por SHA-256.
  - O que resta do Plano 2 e homologacao com dados reais (Marco B: primeiro
    processo PJe integral), que depende do acesso do advisor.

- **2026-07-10 — Marco A (Fundacao do agente local) concluido.** Plano 1 do
  roadmap de autos/conectores executado integralmente
  (`docs/superpowers/plans/2026-07-10-fundacao-automacao-judicial-agente-local.md`):
  - Contratos neutros de sistema (`app/connectors/contracts.py`):
    `CourtReaderDriver`/`FilingDriver` sem dependencia de PJe.
  - `ProcessoInstancia` modela 1o/2o grau por processo; migracao Alembic
    `a6c4d8e2f1b0` aplicada.
  - Agente Windows local (`python -m app.local_agent pair|login|run`):
    pareamento one-time (10 min), token no keyring (hash-only no banco,
    revogavel), perfil Playwright persistente por (sistema, tribunal, grau)
    em `%LOCALAPPDATA%\Causor\profiles`.
  - Protocolo de comandos idempotente (claim unico via SKIP LOCKED,
    heartbeat, complete/fail com auditoria) + API `/agent/*`.
  - Storage privado de documentos (localdev/S3) com URL pre-assinada de
    15 min; backend recomputa SHA-256 na ingestao.
  - UI: secao "Agente local" em Configuracoes (parear, status
    Online/Offline, revogar).
  - O backend hospedado nao abre mais navegador de tribunal; quem executa
    Playwright e o agente na maquina do advogado.
  - Proximo: Plano 2 (autos integrais com driver fake) e infra do Plano 3;
    conectores reais PJe/eproc/e-SAJ/Projudi dependem dos acessos do advisor.

- SOR + prazo engine deterministico implementados.
- Captura real via DJEN/Comunica + DataJud funcionando.
- Supabase Postgres e Supabase Auth funcionando com `causorai@gmail.com`.
- Backend valida JWT, isola por `escritorio_id` e o frontend envia Bearer token.
- IA roda em Claude:
  - chat operacional: `claude-haiku-4-5`;
  - classificacao de intimacao: `claude-haiku-4-5`;
  - redacao de minuta: `claude-sonnet-5`.
- PJe assistido iniciado: protocolo prepara ate `ready_to_sign`; assinatura/envio
  final ainda fica com o advogado no PJe/PJeOffice.
- Captura agendada possui retry exponencial limitado, recuperacao de jobs
  interrompidos e codigo de saida nao-zero em falha definitiva.
- CI valida Ruff, pytest, Vitest e build do Next.js.
- Testes do frontend cobrem autenticacao HTTP e os principais contratos do
  fluxo de captura, prazo, aprovacao e protocolo assistido.
- PDF de protocolo com papel timbrado por escritorio: logo + cabecalho +
  rodape configuraveis em Configuracoes; preview via "Baixar PDF" na minuta;
  o job de protocolo anexa esse mesmo PDF.

## Chaves/servicos

- `CAUSOR_DATABASE_URL` - Supabase Postgres.
- `CAUSOR_DATAJUD_API_KEY` - DataJud.
- `ANTHROPIC_API_KEY` - Claude.
- `CAUSOR_SUPABASE_JWT_SECRET` - Supabase Auth/JWT.

## Como o MNI reordena o Plano 3 (Tasks 6-9)

As Tasks 6-9 (`superpowers/plans/2026-07-10-conectores-reais-multissistema.md`)
sao **4 sistemas x (reader + filing) = 8 entregas**, cada uma travada num
*external gate* — conta de tribunal autorizada, que depende do advisor. Elas
estao paradas por isso ha semanas.

O MNI e **um** par de drivers cobrindo N tribunais, travado num gate que o
proprio Causor conduz (o oficio). E o `MniFilingDriver` reusa a MESMA
credencial, endpoint, vault, perfis e erros canonicos ja construidos para
leitura — e trabalho incremental sobre fundacao pronta, nao um conector novo.

O que muda em cada frente:

| Frente | Situacao |
|---|---|
| **Leitura** (metade "reader" das Tasks 6-9) | **Superada onde ha MNI.** O `MniReader` implementa o mesmo `CourtReaderDriver`; o pipeline de integridade nao sabe a fonte. |
| **Protocolo** (metade "filing") | **Nao superada ainda.** Hoje so o agente local protocola. O `MniFilingDriver` nao existe. |
| **Tribunal sem MNI** | Tasks 6-9 seguem validas como fallback. O roteamento ja cai no agente sozinho. |

**Ressalva honesta:** a varredura testou padroes de URL do **PJe**. A ausencia
de evidencia para eproc/e-SAJ/Projudi e limite do metodo, nao prova de que
esses sistemas nao expoem MNI. Antes de investir nas Tasks 7-9, verificar se o
tribunal daquele sistema atende por MNI.

Consequencia: as Tasks 6-9 **descem de prioridade** e deixam de ser o caminho
critico. Nenhuma delas e cancelada — todas continuam sendo o fallback para
tribunal onde o MNI nao entregar.

## Ainda falta para MVP real

Sao **duas trilhas paralelas**, nao uma fila. A trilha do piloto nao depende de
terceiro e entrega valor sozinha; a trilha MNI espera o deferimento do oficio.
O piloto **nao espera tribunal** — o agente local captura hoje, sem credencial
nenhuma.

### Trilha do piloto (sem gate externo)

1. Publicar backend e frontend com CI verde.
2. Configurar em producao o cron que chama `capture-due` e alertar quando seu
   codigo de saida for diferente de zero.
3. Validar o Vault Supabase no ambiente publicado (referencias de assinatura
   `cloud_cert` e senhas MNI; o cofre de sessao de tribunal foi removido —
   sessao vive so no agente local, Plano 3 Task 3).
4. Adicionar monitoramento externo do backend, cron e jobs `failed`.
5. Executar um piloto ponta a ponta com OAB e dados reais, **pelo agente
   local**: capturar, prazo, minuta e revisao nao dependem de MNI.
6. ~~Alertas de prazo por e-mail ou WhatsApp.~~ **Implementado em 2026-07-30**
   (`app/alertas/`): regra unica do radar (`radar.prazos_em_alerta`, consumida
   tambem pelo `GET /alertas`), notificacao com dedupe por `(prazo, nivel)` na
   tabela `notificacao_prazo`, envio por SMTP com fallback para log
   (`ConsoleSender`) e comando `python -m app.cli notificar-prazos` para o cron.
   **Falta em producao:** aplicar a migration `a3e7b1c9d2f8`, definir
   `CAUSOR_SMTP_HOST/PORT/USER/FROM` + `CAUSOR_SMTP_PASSWORD` no `.env` da VPS e
   agendar o comando. Sem SMTP configurado o aviso cai no log e nada quebra.
   WhatsApp entra depois como um segundo `AlertSender` — so esse arquivo muda.

### Trilha MNI (aposta paralela — testar viabilidade antes de investir)

7. **Consultar por escrito se CNPJ privado pode ser credenciado** — duas DTIs
   de tribunal e `integracaopdpj@cnj.jus.br`. Custo: dois e-mails; resolve a
   duvida de vez (ver secao 0 de
   [`areas/mni-credenciamento.md`](areas/mni-credenciamento.md)). Se a resposta
   for negativa, esta trilha inteira morre e o agente local vira o unico
   caminho — o que **nao** bloqueia o piloto.
   Deferida a consulta, **solicitar o credenciamento** no tribunal do piloto.
   Oficio redigido, com placeholders, em
   [`areas/oficio-credenciamento-mni.md`](areas/oficio-credenciamento-mni.md);
   endpoints e ressalvas em
   [`areas/mni-credenciamento.md`](areas/mni-credenciamento.md).
8. Deferido: rodar `RUN_MNI_LIVE=1` e confirmar que o tribunal entrega **o
   teor** dos documentos — e onde mais tribunais falham na pratica.
9. **So entao** construir o `MniFilingDriver` (`entregarManifestacaoProcessual`).

   *Nao antecipar este item.* Protocolo e irreversivel e a regra e nunca marcar
   "protocolada" sem comprovante verificado — nao da para projetar a
   verificacao do comprovante sem ter visto um comprovante real. Tres respostas
   do oficio mudam o desenho: se a autenticacao exige mTLS (pergunta 2), se o
   credenciamento dispensa certificado (5) e se a resposta traz o comprovante
   (6). Construir contra simulador proprio antes disso e codificar as nossas
   suposicoes e chamar de verificado — exatamente o erro de 21/07, agora na
   metade irreversivel do sistema.

### Fallback (so quando o MNI nao cobrir o tribunal do piloto)

10. Fechar um unico conector Playwright real ate a tela de assinatura
    (Plano 3 Task 6), escolhendo tribunal, grau e tipo de peticao.
11. Integracao com certificado em nuvem, se o piloto exigir envio final
    automatizado **e** o credenciamento MNI nao dispensar a assinatura.

## Ordem de execucao

> **SUBSTITUIDA EM 2026-07-30 por
> [`areas/plano-90-dias-2026-07-30.md`](areas/plano-90-dias-2026-07-30.md).**
> A pesquisa de 30/07 ([`areas/rota-produto-2026-07-30.md`](areas/rota-produto-2026-07-30.md))
> mostrou que o CNJ esta unificando consulta processual e peticionamento
> intercorrente no **jus.br** (Res. CNJ 455/2022 + 624/2025; ~39 tribunais ja
> integrados), o que rebaixa os conectores por sistema (Tasks 6-9) a fallback, e
> que os perfis MNI confirmados **nao cobrem o TJTO**, tribunal do piloto. A
> ordem abaixo fica como registro historico; siga o plano de 90 dias.

As duas trilhas acima intercaladas no tempo real. A consulta ao tribunal sai
primeiro porque e a de maior latencia e menor esforco — **mas o piloto nao
espera por ela.** O caminho critico e o piloto real; o MNI e aposta paralela.

1. Enviar a consulta de viabilidade do MNI + o oficio (nao bloqueia nada abaixo
   enquanto tramita).
2. Publicar backend e frontend com CI verde.
3. Provisionar o primeiro escritorio conforme `onboarding-piloto.md`.
4. Ativar o cron e acompanhar ao menos dois ciclos de captura.
5. Validar captura, prazo e minuta com o advogado — pelo agente local, que
   funciona hoje.
6. Deferido o credenciamento: cadastrar a credencial, rodar `RUN_MNI_LIVE=1` e
   deixar o roteamento migrar a leitura para `fonte="mni"` sozinho.
7. Concluir um protocolo real — via MNI se a resposta do tribunal permitir,
   senao assistido pelo agente.

Nao ampliar para novos tribunais, billing ou RAG antes dessa validacao.

## Decisoes de custo de IA

Nao usar modelos premium em teste. O custo padrao fica:

- Haiku para chat e classificacao.
- Sonnet para minuta.

Modelos mais caros ficam fora do caminho padrao e so devem ser reintroduzidos
se houver uma tarefa juridica que Sonnet nao resolva bem.
