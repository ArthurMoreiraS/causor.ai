# PRD — Causor

> Documento estratégico. Para estado implementado e ordem de execução atual,
> use `docs/estado.md`.

**Produto:** Causor — Agente Operacional Jurídico
**Categoria:** SaaS vertical de IA + automação ("computer use") para operação processual no Brasil
**Análogo de referência:** [Handle.ai](https://usehandle.ai) (agentes que operam portais fragmentados e automatizam o back-office de seguros) — transposto para o jurídico brasileiro.
**Documento:** PRD vivo. Versão 0.4 — 22/07/2026.
**Status do produto:** MVP com a fatia *captura → prazo → minuta → aprovação →
protocolo assistido* pronta e três avanços estruturais desde a v0.3:

1. **Arquitetura de agente local** (Plano 1 concluído): o backend hospedado
   **não abre mais navegador de tribunal**. Quem executa a automação
   (Playwright) é um agente pareado na máquina Windows do advogado, com a
   credencial dele e perfis persistentes por (sistema, tribunal, grau). Separa
   o dado sensível da nuvem e alinha com a responsabilidade OAB.
2. **Leitura íntegra dos autos + contexto citado + gate fail-closed** (Plano 2
   concluído): captura do processo inteiro com **prova de completude**
   (enumeração dupla + fingerprint SHA-256, versões imutáveis por hash),
   OCR por página, trechos citáveis e resumo com **citações verificadas**. A
   minuta e o protocolo **bloqueiam (HTTP 409)** sem um dossiê "ready"; o
   override do advogado é de uso único, expira em 30 min, exige justificativa
   e gera auditoria. O drafter passou a receber os autos com rótulos
   `[DOC-N p.M]` — não só o teor da intimação.
3. **Canal oficial MNI** (Modelo Nacional de Interoperabilidade do CNJ,
   2026-07-21): cliente SOAP que lê os autos (`consultarProcesso`) e pode
   **protocolar** (`entregarManifestacaoProcessual`) direto no tribunal usando
   o cadastro do advogado como assinatura eletrônica válida (Lei 11.419/2006
   art. 1º §2º III) — potencial atalho para dispensar PJeOffice/certificado.
   14 perfis (tribunal, grau) verificados por varredura; falta só o credenciamento (ofício
   gratuito à DTI do tribunal).

O envio final em produção ainda é confirmado pelo advogado enquanto os
conectores reais não são homologados. O switch de provedor de LLM
(`CAUSOR_LLM_PROVIDER`) existe no código, mas testes e produção rodam com
Claude (ver 5.4).

> Este PRD descreve a direção estratégica. O estado implementado e a ordem de
> execução ficam em `docs/estado.md`.

---

## 1. Visão

Ser o "funcionário operacional digital" do escritório de advocacia brasileiro: um agente que **captura** intimações nos diários oficiais, **calcula** o prazo correto de forma determinística, **minuta** a peça cabível e **protocola** dentro do tribunal — com trilha de auditoria imutável e o advogado no controle.

A tese, igual à do Handle.ai: um setor com **sistemas fragmentados** (PJe, e-SAJ, Projudi, EPROC = os "100+ portais de seguradoras") e **trabalho repetitivo de back-office** (monitorar publicações, controlar prazos, peticionar) hoje feito por estagiários e paralegais — caro, escalável apenas com headcount e propenso a erro. Perder prazo é falta grave (responsabilidade civil do advogado), o que torna a dor **crítica** e o ROI **mensurável**.

**Tagline interna:** *"Não monitoramos publicações. Operamos o processo."*

---

## 2. Problema

| Dor | Quem sente | Custo hoje |
|---|---|---|
| Monitorar diários e identificar o que exige ação | Estagiário/paralegal | Horas/dia de leitura manual |
| Calcular prazo correto (dias úteis, feriado local, recesso, suspensão) | Advogado/paralegal | Erro = perda de prazo = malpractice |
| Redigir peças repetitivas (manifestações, contestações modelo) | Advogado júnior | Horas por peça, retrabalho |
| Protocolar em portais lentos e fragmentados, com certificado e captcha | Advogado | Trabalho braçal, login por sistema |
| Provar o que foi feito e quando (responsabilidade OAB) | Sócio/compliance | Sem trilha confiável |

O concorrente de monitoramento (Astrea, Projuris, Legal One, Digesto, Escavador) resolve só a **primeira linha** (capturar e avisar). O resto continua manual. **O fosso do Causor é executar o resto.**

---

## 3. Mercado e cliente

- **Mercado:** Brasil.
- **Cliente inicial (ICP):** escritórios pequenos/médios — do advogado autônomo a ~50 advogados — contencioso de massa/repetitivo (trabalhista, consumidor, cível, previdenciário).
- **Por que esse recorte:** alto volume de prazos, peças padronizáveis, dor financeira direta na folha de paralegais, ciclo de venda curto.
- **Expansão futura:** departamentos jurídicos de empresas (in-house) e escritórios grandes (módulo de governança/auditoria).

### Personas

1. **Sócio/gestor do escritório** — quer reduzir risco de perda de prazo e custo de paralegal; compra. KPI: nº de quase-erros, horas/mês economizadas.
2. **Advogado responsável (OAB)** — assina e responde profissionalmente; precisa do **gate de aprovação** e da auditoria. Não cede controle de ato irreversível.
3. **Paralegal/estagiário** — opera a fila do dia a dia; o Causor vira o "colega" que adianta o trabalho pesado.

---

## 4. Posicionamento vs. Handle.ai

| Eixo | Handle.ai (seguros) | Causor (jurídico) |
|---|---|---|
| System of Record | Unifica apólices/sinistros de 100+ portais | Unifica processos/prazos/andamentos de múltiplos tribunais |
| Captura | Portais de seguradoras | **APIs oficiais** DJEN/Comunica + DataJud + **MNI** (autos); agente local como fallback (sem scraping em massa) |
| Completude | — | **Prova de integridade** dos autos (enumeração dupla + SHA-256 + gate fail-closed) |
| Cálculo crítico | Regras de cobertura | **Motor de prazos determinístico** (CPC dias úteis, feriados, recesso) |
| Ação autônoma | Cotar/operar o portal | **Protocolar** via MNI ou agente local (computer use + gate humano) |
| Diferencial | Agir, não só agregar | Agir, não só monitorar |
| Guarda-corpo | — | Gate de aprovação OAB + auditoria imutável |

O moat **não** é capturar publicação (commodity). É a **execução autônoma com
responsabilidade controlada** — e, no acesso aos autos, a **prova de que o
conjunto veio inteiro**.

### 4.1 Leitura competitiva: Enter / Judit (mercado brasileiro)

A **Enter** virou o primeiro unicórnio de IA jurídica do Brasil (rodada de
~R$ 500 mi, maio/2026) **comprando** a camada de dados da **Judit** e vendendo
inteligência em cima. Isso confirma que o valor **não** está em capturar
processo — é commodity. Mas a Enter atende contencioso de massa do **lado do
réu** (Bradesco, Nubank, Itaú, Mercado Livre): clientes com ERP jurídico
próprio, para quem os autos do tribunal **não são a única fonte**, e que
toleram 2% de captura incompleta como ruído estatístico.

O ICP do Causor é o oposto: o escritório pequeno **só tem** os autos do
tribunal, **não tolera** captura incompleta (falta uma peça = minuta errada =
prazo perdido = *malpractice*) e precisa que alguém **protocole**, não que
avise. Dois buracos que nenhum vendor de dados (Judit, Escavador, Digesto)
vende — **garantia de completude** e **protocolo** — são exatamente o Causor.
Detalhe em [`docs/areas/acesso-aos-autos-mercado.md`](../areas/acesso-aos-autos-mercado.md).

**Escada de acesso aos autos** (melhor → fallback): **(1) MNI** — oficial,
gratuito, padronizado pelo CNJ, lê *e* protocola; custo é um ofício. **(2)
Agente local** — máquina pareada do advogado, cobre tribunal sem MNI e
protocola hoje. **(3) Vendor pago** — só se um tribunal falhar nos dois
caminhos acima e o cliente justificar o custo; nunca como base da arquitetura.

---

## 5. Estado atual do produto (o que já existe)

Implementado na branch `main`, com validação automática de backend e frontend
no CI. Não manter contagens de testes neste documento; elas mudam a cada
entrega e devem ser consultadas no workflow mais recente.

### 5.1 System of Record (`backend/app/sor`) — ✅ pronto
Modelos Postgres/SQLite-portáveis para todas as entidades do domínio: `escritorio`, `usuario`, `cliente`, `processo`, `intimacao`, `prazo`, `peticao`, `andamento`, `documento`, `credencial_assinatura` (apenas **referência** ao cofre — nunca o segredo) e `audit_log` (append-only, imutável por convenção/grant).

### 5.2 Motor de prazos (`backend/app/prazo_engine`) — ✅ pronto
Cálculo **determinístico** (`compute_deadline` sobre `ForensicCalendar`): contagem em dias úteis (CPC art. 219) ou corridos, prorrogação do "dia do começo" e da data fatal para o próximo dia útil, feriados e recesso. Código testável — não é chamada de IA.

### 5.3 Captura (`backend/app/capture`) — ✅ pronto (APIs oficiais)
Clientes **DJEN/Comunica** (intimações) e **DataJud** (metadados/andamentos), normalização e orquestração `poll_oab` (captura por OAB/UF, dedupe por `fonte/fonte_id`, vincula processo, dispara cálculo de prazo). Testes de integração ao vivo opt-in (`RUN_LIVE=1`).

### 5.3.1 Leitura íntegra dos autos + contexto citado (`backend/app/autos`, `backend/app/context`) — ✅ pronto (Plano 2)
Captura do **processo inteiro** com **prova de completude**: enumeração
inicial/final com fingerprint SHA-256, versões imutáveis por hash, HTML
disfarçado de PDF rejeitado por magic bytes; só marca `complete` com
enumerações idênticas e todo item verificado. Extração de texto por página com
OCR (Tesseract `por`) apenas onde não há camada textual; trechos citáveis
(chunks por página) com busca lexical (FTS português no Postgres); resumo
estruturado por documento com **citações verificadas** contra os chunks (quote
inventado marca o resumo `failed`). O `ContextoProcesso` só fica `ready` com
1º e 2º grau completos (ou `not_applicable` com evidência) + 100% dos arquivos
extraídos e resumidos; o drafter recebe inventário + excertos rotulados
`[DOC-N p.M]`. **Gate fail-closed:** minuta e protocolo retornam **HTTP 409**
sem contexto `ready`/atual; override do advogado é de uso único, expira em
30 min, exige justificativa (20–1000 chars) e gera auditoria.

### 5.3.2 Canal oficial MNI (`backend/app/connectors/mni`) — ✅ pronto; ⛔ live bloqueado no credenciamento
Cliente SOAP próprio (httpx + lxml, sem zeep) para o **Modelo Nacional de
Interoperabilidade** do CNJ (v2.2.2), com perfis de endpoint por tribunal/grau
**fail-closed** e segredos leak-safe. Lê os autos (`consultarProcesso`,
`incluirDocumentos=true`) pelo mesmo pipeline de integridade da 5.3.1, roteado
por `CapturaAutos.fonte` ("mni" | "agente"). A operação
`entregarManifestacaoProcessual` permite **protocolar direto no tribunal**
usando o cadastro do advogado como assinatura eletrônica válida
(Lei 11.419/2006 art. 1º §2º III) — potencial atalho para dispensar
PJeOffice/certificado, a confirmar por tribunal no credenciamento. Varredura de
2026-07-22 confirmou **14 perfis (tribunal, grau)** em 9 tribunais (TJs estaduais + TRF5/TRF6). Falta só o
**credenciamento** (ofício gratuito à DTI); com `RUN_MNI_LIVE=1` verde, o
roteamento escolhe `fonte="mni"` sozinho. Detalhe em
[`docs/areas/mni-credenciamento.md`](../areas/mni-credenciamento.md).

### 5.4 Camada de agente (`backend/app/agent`) — ✅ parcial
- **Classificador** (`claude-haiku-4-5`, structured output): interpreta o teor da intimação → tipo do ato, peça cabível, prazo em dias, dias úteis vs. corridos, confiança. O **cálculo da data continua determinístico**.
- **Drafter:** gera rascunho de peça a partir do teor + classificação.
- **Assistente agêntico** (`chat`): loop de tool use com ferramentas de **leitura** (listar prazos, buscar processo, ler intimação) e **proposta de ação** (gerar minuta, marcar prazo cumprido, aprovar petição). **Protocolar nunca é ferramenta do agente.** Segredos e rascunhos sensíveis não entram no contexto do modelo.
- **Switch de provedor de LLM** (`CAUSOR_LLM_PROVIDER`, ver `IA.md`): classificador e drafter passam por `get_provider()`, que suporta alternar entre `ClaudeProvider` (produção) e `OpenAICompatProvider` (Groq/Ollama). Na prática, **não é usado para teste** — testes e desenvolvimento também rodam com Claude, para manter a qualidade de classificação/redação consistente com produção. O chat agêntico permanece **Claude-only** por depender de tool-calling nativo.

### 5.5 API (`backend/app/api`) — ✅ pronto para o MVP
FastAPI: dashboard operacional, fila de revisão (com risco/dias para vencer), listagens (intimações, processos, prazos, petições), `POST /capture/oab`, geração de minuta, **gate de aprovação** (`approve` → `protocolar`), revisão inline de prazo (`PATCH /prazos`), `cumprir`, `chat` e `GET /audit`. Toda mutação gera evento de auditoria.

### 5.6 Frontend (`frontend`, Next.js + React) — ✅ pronto para o MVP
Dashboard, inbox de intimações, painel de prazos com risco, fila de aprovação, **painel do assistente agêntico** (cards de ação com confirmação humana), **painel de auditoria**, modal de **captura real por OAB**, revisão inline de data de prazo. Arquitetura offline-first (erros claros quando o backend/IA estão indisponíveis). Reforma visual concluída em 05–06/07/2026 na linha do Handle.ai: paleta quase monocromática (teal removido, cor só como semântica de risco/sucesso), listas viradas em tabelas com divisores hairline, tipografia display + micro-labels em mono caixa alta. Mudança de apresentação apenas — nenhuma rota, dado ou comportamento mudou.

### 5.7 Guarda-corpos já no código
- **Gate humano** antes de qualquer ato irreversível (protocolo exige `aprovada`).
- **Segredos fora do prompt e dos logs** (o SOR guarda uma referência; a credencial em si pode viver no vault do Causor ou num vendor terceiro delegado — não é mais regra fixa).
- **Auditoria imutável** em toda mutação de estado.
- **APIs oficiais antes de scraping** na captura.

### 5.7.1 Agente local e framework de conectores (`backend/app/connectors`, `app/local_agent`) — ✅ base pronta (Planos 1 e 3)
Contratos neutros de sistema (`CourtReaderDriver`/`FilingDriver`, sem dependência
de PJe), `ProcessoInstancia` (1º/2º grau por processo), agente Windows local
(`python -m app.local_agent pair|login|run`) com pareamento one-time, token no
keyring (hash-only no banco, revogável) e perfil Playwright persistente por
(sistema, tribunal, grau). Protocolo de comandos idempotente (claim único via
`SKIP LOCKED`, heartbeat, complete/fail auditado). Do Plano 3: perfis de
conector versionados + registry fail-closed, login de tribunal como comando na
fila do agente com `CourtSessionState` derivado (o cofre de sessão do backend
foi **removido** — sessão vive só no agente), simuladores sanitizados + harness
de validação live, ações reais migradas para rodar no agente, status persistido
de validação/cobertura e assistente de minuta JIT com UI unificada "Acesso aos
tribunais".

### 5.8 O que ainda **não** existe (e por que)
- **Os quatro conectores reais** (PJe/eproc/e-SAJ/Projudi) validados até o ato
  final. Todo o arcabouço acima foi construído e testado contra **simuladores**;
  a homologação com tribunal real (Marco B/C) está **bloqueada no acesso de
  credenciais/processo de teste que o advisor precisa fornecer** — é o caminho
  crítico, não código faltando.
- **Credenciamento MNI** deferido em ao menos um tribunal (ofício gratuito, em
  andamento) — destrava leitura oficial *e*, possivelmente, protocolo sem
  certificado.
- Assinatura/envio automáticos por certificado em nuvem (fallback caso o MNI
  não dispense assinatura no tribunal do piloto).
- Worker dedicado de produção (Celery/RQ); hoje os jobs persistem no SOR e o
  executor roda como processo/CLI agendado.
- Billing.
- Deploy definitivo e monitoramento externo (cron `capture-due`, jobs `failed`).

### 5.9 Endpoints da API (FastAPI)
- `GET /health`
- `GET /me`
- `GET /dashboard/operational`
- `GET /review/queue`
- `GET /processos`
- `GET /intimacoes`
- `GET /prazos`
- `GET /peticoes`
- `GET /jobs`
- `GET /audit`
- `POST /intimacoes/{id}/draft`
- `POST /peticoes/{id}/approve`
- `POST /peticoes/{id}/protocolar/async`
- `POST /peticoes/{id}/protocolar/confirmar`

> Lista de referência; para o contrato atualizado, consulte
> `http://localhost:8000/docs` (Swagger) ou `backend/app/api/`.

---

## 6. Escopo do produto

### 6.1 Em escopo (now → MVP completo)
Fechar a fatia vertical ponta a ponta em **um** tribunal: captura DJEN/DataJud → prazo determinístico → minuta Claude → **protocolo real com gate** → auditoria. Pilotos com 2–3 escritórios.

### 6.2 Fora de escopo (por ora)
A3 (token físico — não automatizável), múltiplos tribunais simultâneos, agentes além do fluxo principal (cobrança/financeiro), BI avançado, app mobile nativo.

---

## 7. Features

Legenda de estado: ✅ pronto · 🟡 parcial · 🔭 nova ideia (proposta neste PRD) · ⛔ não iniciado.

### 7.1 Núcleo (existente / em fechamento)

| # | Feature | Estado | Descrição |
|---|---|---|---|
| F1 | Captura por OAB (DJEN + DataJud) | ✅ | Puxa intimações e metadados por OAB/UF, normaliza e grava no SOR. |
| F2 | Motor de prazos determinístico | ✅ | Data fatal por CPC, dias úteis, feriados, recesso. |
| F3 | Classificação da intimação por IA | ✅ | Tipo do ato, peça cabível, dias, confiança. |
| F4 | Geração de minuta | ✅ | Rascunho a partir do teor com templates do escritório. |
| F5 | Gate de aprovação OAB | ✅ | Nenhum protocolo sem aprovação humana. |
| F6 | Auditoria imutável | ✅ | Toda ação vira evento consultável. |
| F7 | Assistente agêntico (chat) | ✅ | Lê o SOR e **propõe** ações (confirmação humana); nunca protocola. |
| F8 | Painel de prazos com risco | ✅ | Vencido/alto/médio/baixo + dias para vencer. |
| F9 | **Leitura íntegra dos autos + prova de completude** | ✅ | Enumeração dupla + SHA-256 + OCR + gate fail-closed (409 sem contexto ready). |
| F10 | **Contexto citado para a minuta** | ✅ | Resumos com citações verificadas; drafter recebe `[DOC-N p.M]`. |
| F11 | **Agente local + framework de conectores** | ✅ | Agente pareado na máquina do advogado; perfis versionados, simuladores, harness live. |
| F12 | **Canal oficial MNI** (leitura + protocolo) | 🟡 | Cliente SOAP pronto e 14 perfis verificados; live bloqueado no credenciamento. |
| F13 | **Conectores reais** (PJe/eproc/e-SAJ/Projudi) | ⛔ | Arcabouço pronto; homologação bloqueada no acesso do advisor (Marco B/C). |
| F14 | **Assinatura em nuvem** | 🟡 | Vault existe; ICP-Brasil em nuvem só se o MNI não dispensar assinatura no piloto. |
| F15 | Jobs persistidos e captura agendada | 🟡 | Executor local/CLI pronto; falta worker dedicado de produção. |
| F16 | Auth + multi-tenant + billing | 🟡 | Auth e isolamento (Supabase) prontos; billing não iniciado. |

### 7.2 Novas ideias de feature (propostas)

Agrupadas por tema. Cada uma indica o **porquê** (valor) e um **esboço** do como.

#### A. Confiança e redução de risco (reforçam o moat)
- 🔭 **A1. Detector de prazo perdido / "near-miss radar".** Cruza intimações capturadas com prazos calculados e dispara alerta escalonado (e-mail/WhatsApp/push) em D-3, D-1 e no dia, com escalonamento para o sócio se ninguém agir. *Valor:* transforma "perdi um prazo" em "fui avisado 3 vezes". *Como:* job na fila (F11) + canal de notificação.
- 🔭 **A2. Segunda opinião do prazo (dupla checagem IA + determinístico).** Quando a confiança da classificação < limiar, o sistema marca o prazo como "requer revisão humana" e mostra o teor lado a lado com a sugestão. *Valor:* erros de classificação não viram erros de prazo silenciosos.
- 🔭 **A3. Cobertura de captura ("nada caiu no vão").** Reconciliação periódica DataJud × DJEN × processos cadastrados para detectar processo sem captura ativa ou intimação órfã. KPI exibido: "% de processos com monitoramento confirmado".
- 🔭 **A4. Simulador de contagem de prazo.** Ferramenta no frontend onde o advogado insere data de publicação + tipo de prazo e vê a contagem explicada (quais dias foram pulados e por quê). Vira também ferramenta de marketing/aquisição (calculadora pública).

#### B. Produtividade da minuta
- ✅ **B1. Biblioteca de templates do escritório.** Criação e edição de
  modelos por tipo de peça e área.
- 🔭 **B2. Memória de teses / RAG do escritório.** Indexa peças passadas e decisões favoráveis; a minuta cita precedentes internos e jurisprudência relevante. *Como:* embeddings + recuperação, com citação rastreável (sem alucinar).
- 🔭 **B3. Editor colaborativo com diff e versões.** O advogado edita a minuta; o sistema guarda versões e mostra o que mudou entre IA e final — alimenta o aprendizado de templates.
- 🔭 **B4. Pacote de protocolo automático.** Monta automaticamente os anexos exigidos (procuração, documentos do processo, custas) a partir do SOR/documentos.

#### C. Operação e escala
- ✅ **C1. Fila do dia ("worklist") priorizada por risco.** Tela única para
  organizar o trabalho operacional do dia.
- 🔭 **C2. Distribuição/atribuição.** Roteia intimações para o advogado responsável por cliente/área; SLA por item.
- 🟡 **C3. Captura agendada multi-OAB.** Executor e agendamento local prontos;
  falta operação no ambiente definitivo.
- 🔭 **C4. Conectores além do PJe.** e-SAJ (TJSP — maior mercado), depois Projudi/EPROC. Cada um isolado e testável.

#### D. Governança, compliance e relação com o cliente
- 🔭 **D1. Relatório de auditoria exportável (PDF/CSV).** "O que o agente fez no processo X" — prova para OAB/cliente. Sobre o `audit_log` já existente.
- 🔭 **D2. Portal/relatório do cliente final.** Resumo em linguagem leiga do andamento dos processos do cliente — gerado por IA a partir dos andamentos. *Valor:* retém cliente, reduz "advogado, e o meu processo?".
- 🔭 **D3. Gate configurável por confiança/valor.** O sócio define regras: "autoprotocola manifestações simples com confiança > 0.95; tudo acima de X exige aprovação". Implementa a "remoção progressiva do gate conforme a confiança cresce" sem nunca tirar o gate do código.
- 🔭 **D4. Trilha assinada/encadeada (hash chain).** Cada evento de auditoria encadeia o hash do anterior — auditoria à prova de adulteração de verdade.

#### E. Inteligência de negócio
- 🔭 **E1. Dashboard de ROI.** "Horas economizadas, prazos cumpridos no prazo, quase-erros evitados" — vende o produto para dentro do escritório (alinha com o KPI do sócio).
- 🔭 **E2. Previsão de carga.** Antecipa picos de prazos por área/semana para planejar a equipe.
- 🔭 **E3. Benchmark anônimo.** Tempo médio de resposta a intimações vs. mercado (com dados agregados/anonimizados).

---

## 8. Roadmap (build order)

Mantém a ordem do plano: fatia vertical primeiro, depois expansão.

**Fase 0 — Destravar o acesso ao tribunal (caminho crítico, now):** obter o
**credenciamento MNI** em um tribunal com processo ativo do piloto (ofício
gratuito) e/ou as **credenciais reais do advisor** para PJe/eproc/e-SAJ/Projudi
+ um processo de teste seguro. Sem isso, os conectores (F12/F13) não saem do
simulador — é o único gargalo real. Em paralelo: escolher o ambiente definitivo
e operar a captura agendada. *Wizard-of-Oz aceitável:* rodar captura + prazo +
minuta automáticos com protocolo manual enquanto o conector homologa.

**Fase 1 — Confiança e operação:** A1 (radar de prazo), A2 (dupla checagem),
D1 (relatório de auditoria) e worker dedicado.

**Fase 2 — Escala de captura e tribunais:** C3 (captura agendada), C4 (e-SAJ), A3 (cobertura), D3 (gate configurável).

**Fase 3 — Diferenciação:** B2 (RAG de teses), D2 (portal do cliente), E1 (ROI), billing completo.

> Regra: não ampliar escopo à frente desta ordem sem decisão explícita.

---

## 9. Métricas de sucesso

**MVP (pilotos):**
- ≥ 90% das intimações relevantes capturadas.
- ≥ 99% de prazos corretos nos casos testados (meta do prazo engine).
- Minutas aprovadas com **edição mínima**.
- ≥ 1 protocolo real concluído via gate em produção.

**Produto (pós-MVP):**
- Horas/mês economizadas por escritório (autorreportado + medido).
- Nº de quase-erros (prazos sinalizados a tempo) — North Star de confiança.
- Taxa de minuta aceita sem reescrita.
- Retenção mensal de escritórios; expansão de OABs monitoradas por conta.

---

## 10. Restrições não-negociáveis (definem a arquitetura)

1. **Fazer funcionar vale mais que pureza de custódia.** Certificados, senhas de `.pfx` e credenciais de assinatura/sessão podem ser delegados a um vendor terceiro de confiança (ex.: Escavador, Judit, um provedor de assinatura em nuvem) para leitura dos autos ou para assinatura/protocolo, sempre que isso for o caminho mais rápido até um fluxo que funciona. Não existe mais regra de que a credencial precisa ficar só na máquina do advogado ou só no vault do Causor — o advogado quer saber se funciona, não onde o byte mora. Preferência por **certificado em nuvem** (BirdID, VIDaaS, Certisign Cloud, SafeID) por conveniência; A1 cifrado como fallback; A3 continua inviável de automatizar, com ou sem vendor. Segredos continuam fora de prompt de LLM e de log de aplicação — isso é prevenção de vazamento, independe de custódia.
2. **Gate de aprovação humana antes de qualquer ato irreversível** (protocolo). O advogado segue responsável (OAB). O gate é desengatado conforme a confiança cresce — **nunca removido do código**.
3. **Trilha de auditoria imutável desde o dia 1.**
4. **APIs oficiais antes de scraping** (DJEN/Comunica + DataJud). Computer use/Playwright só para **ação**, com human-in-the-loop quando captcha/layout travar.

---

## 11. Riscos e mitigação

| Risco | Impacto | Mitigação |
|---|---|---|
| Certificado/assinatura (gargalo de viabilidade) | Sem isso não há protocolo autônomo | Validar 1 provedor de certificado em nuvem cedo (F10). |
| Captcha / mudança de layout no tribunal | Quebra o conector | Determinístico + fallback computer-use + human-in-the-loop; começar por 1 sistema. |
| Responsabilidade OAB | Risco jurídico ao cliente | Gate + auditoria imutável desde o dia 1. |
| Concorrência de monitoramento | Comoditização | Competir em **execução autônoma**, não em captura. |
| Alucinação na minuta/classificação | Erro material | Dupla checagem (A2), confiança explícita, gate, RAG com citação rastreável (B2). |
| Mudança nas APIs do CNJ | Quebra de captura | Chave pública DataJud lida em runtime; testes de integração ao vivo. |

---

## 12. Perguntas em aberto (para decisão)

1. **Primeiro tribunal do conector:** priorizar tribunal com **MNI já verificado** (TJPE, TJPI, TJAP, TRF5/TRF6 têm 1º/2º grau confirmados) e processo ativo do piloto, já que o MNI lê *e* pode protocolar sem certificado. e-SAJ/TJSP (maior mercado) fica para o agente local. Decidir com base no piloto disponível.
2. **Provedor de certificado em nuvem** a integrar primeiro (BirdID, VIDaaS, Certisign Cloud, SafeID).
3. **Modelo de cobrança:** por advogado, por OAB monitorada, por volume de protocolos, ou híbrido.
4. **Wizard-of-Oz:** rodar captura + prazo automáticos com protocolo manual nos primeiros pilotos enquanto o conector amadurece?

---

*Próximo passo sugerido: transformar a Fase 0 (conector PJe + cofre/assinatura + templates + fila) em um plano de implementação detalhado.*
