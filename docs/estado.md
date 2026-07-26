# Proximos passos - MVP

## Onde estamos

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

  **Bloqueio unico:** o credenciamento (oficio gratuito a DTI do tribunal).
  Sem credencial nenhum tribunal esta utilizavel de fato — WSDL acessivel nao
  e servico funcional.

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

Caminho critico (nesta ordem):

1. **Solicitar o credenciamento MNI** no tribunal do piloto — destrava
   simultaneamente leitura oficial, protocolo oficial e possivelmente a
   dispensa de assinatura por certificado. Checklist do oficio em
   [`areas/mni-credenciamento.md`](areas/mni-credenciamento.md).
2. Com a credencial em maos, rodar `RUN_MNI_LIVE=1` e confirmar que o tribunal
   entrega **o teor** dos documentos (e onde mais tribunais falham).
3. Construir o `MniFilingDriver` (`entregarManifestacaoProcessual`) sobre a
   fundacao existente — o comprovante vem na resposta, satisfazendo a regra de
   nunca marcar "protocolada" sem comprovante verificado.
4. Executar um piloto ponta a ponta com OAB e dados reais.

Producao e operacao:

5. Configurar em producao o cron que chama `capture-due` e alertar quando seu
   codigo de saida for diferente de zero.
6. Validar o Vault Supabase no ambiente publicado (referencias de assinatura
   `cloud_cert` e senhas MNI; o cofre de sessao de tribunal foi removido —
   sessao vive so no agente local, Plano 3 Task 3).
7. Adicionar monitoramento externo do backend, cron e jobs `failed`.
8. Alertas de prazo por e-mail ou WhatsApp.

Fallback (so quando o MNI nao cobrir o tribunal do piloto):

9. Fechar um unico conector Playwright real ate a tela de assinatura
   (Plano 3 Task 6), escolhendo tribunal, grau e tipo de peticao.
10. Integracao com certificado em nuvem, se o piloto exigir envio final
    automatizado **e** o credenciamento MNI nao dispensar a assinatura.

## Ordem de execucao

1. Enviar o oficio de credenciamento MNI (nao bloqueia nada abaixo enquanto
   tramita).
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
