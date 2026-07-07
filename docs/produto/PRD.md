# PRD — Causor

> Documento estratégico. Para estado implementado e ordem de execução atual,
> use `docs/estado.md`.

**Produto:** Causor — Agente Operacional Jurídico
**Categoria:** SaaS vertical de IA + automação ("computer use") para operação processual no Brasil
**Análogo de referência:** [Handle.ai](https://usehandle.ai) (agentes que operam portais fragmentados e automatizam o back-office de seguros) — transposto para o jurídico brasileiro.
**Documento:** PRD vivo. Versão 0.3 — 07/07/2026.
**Status do produto:** MVP pronto para validação operacional local. A fatia
*captura → prazo → minuta → aprovação → protocolo assistido* existe; o envio
final ainda é realizado pelo advogado no PJe/PJeOffice. Desde a v0.2: reforma
visual do frontend na linha do Handle.ai (paleta monocromática, tabelas
hairline) — mudança de apresentação, sem alteração de escopo ou
comportamento. O switch de provedor de LLM (`CAUSOR_LLM_PROVIDER`) existe no
código, mas não é a prática de teste adotada — testes também rodam com
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
| Captura | Portais de seguradoras | **APIs oficiais** DJEN/Comunica + DataJud (sem scraping) |
| Cálculo crítico | Regras de cobertura | **Motor de prazos determinístico** (CPC dias úteis, feriados, recesso) |
| Ação autônoma | Cotar/operar o portal | **Protocolar** no PJe/e-SAJ (computer use + gate humano) |
| Diferencial | Agir, não só agregar | Agir, não só monitorar |
| Guarda-corpo | — | Gate de aprovação OAB + auditoria imutável + segredos no vault |

O moat **não** é capturar publicação (commodity). É a **execução autônoma com responsabilidade controlada**.

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
- **Segredos fora do prompt e dos logs** (apenas referência ao vault no SOR).
- **Auditoria imutável** em toda mutação de estado.
- **APIs oficiais antes de scraping** na captura.

### 5.8 O que ainda **não** existe
- Conector PJe validado em um tribunal real até a tela de assinatura.
- Assinatura e envio automáticos por certificado em nuvem.
- Worker dedicado (Celery/RQ ou equivalente); os jobs persistem no SOR, mas o
  executor atual roda no processo local/CLI.
- Billing.
- Conectores adicionais (e-SAJ, Projudi, EPROC).
- Deploy definitivo e monitoramento externo.

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
| F9 | **Conector de protocolo PJe** | 🟡 | Base Playwright e fluxo assistido até `ready_to_sign`; falta validação real. |
| F10 | **Cofre + assinatura em nuvem** | 🟡 | Vault existe; integração ICP-Brasil em nuvem ainda não. |
| F11 | Jobs persistidos e captura agendada | 🟡 | Executor local/CLI pronto; falta worker dedicado de produção. |
| F12 | Auth + multi-tenant + billing | 🟡 | Auth e isolamento prontos; billing não iniciado. |

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

**Fase 0 — Validar o MVP vertical (now):** escolher o ambiente definitivo,
operar captura agendada, validar o Vault e concluir o primeiro protocolo PJe
assistido real com gate.

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

1. **Segredos nunca entram em prompt nem em log.** Certificados, senhas de `.pfx` e credenciais de assinatura vivem só no vault. Preferência por **certificado em nuvem**; A1 cifrado como fallback; A3 inviável.
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

1. **Primeiro tribunal do conector:** PJe (padrão CNJ, mais difundido) vs. e-SAJ/TJSP (maior mercado). Decidir com base no piloto disponível.
2. **Provedor de certificado em nuvem** a integrar primeiro (BirdID, VIDaaS, Certisign Cloud, SafeID).
3. **Modelo de cobrança:** por advogado, por OAB monitorada, por volume de protocolos, ou híbrido.
4. **Wizard-of-Oz:** rodar captura + prazo automáticos com protocolo manual nos primeiros pilotos enquanto o conector amadurece?

---

*Próximo passo sugerido: transformar a Fase 0 (conector PJe + cofre/assinatura + templates + fila) em um plano de implementação detalhado.*
