# Plano — SaaS "Agente Operacional Jurídico" (estilo Handle.ai para o jurídico brasileiro)

## Contexto

O objetivo é criar um SaaS inspirado no modelo do **Handle.ai** (agentes de IA + "computer use" que operam portais fragmentados e automatizam o back-office), mas aplicado ao **setor jurídico brasileiro**.

A tese é a mesma do Handle: um setor com **sistemas fragmentados** (PJe, e-SAJ, Projudi, EPROC, etc. = os "100+ portais de seguradoras") e **trabalho operacional repetitivo** (monitorar publicações/intimações, controlar prazos, peticionar, acompanhar andamentos) feito hoje por estagiários e paralegais — propenso a erro e caro. Perder um prazo é falta grave (responsabilidade civil do advogado), o que torna a dor crítica e o ROI mensurável ("devolvemos X horas/mês por funcionário; reduzimos risco de perda de prazo").

**Decisões já tomadas com o usuário:**
- **Mercado:** Brasil
- **Cliente inicial:** escritórios pequenos/médios (advogados autônomos a ~50 advogados)
- **Workflow inicial:** operação processual ponta a ponta — **captura de intimação → cálculo de prazo → minuta de petição → protocolo**
- **Ambição:** agente autônomo ("computer use") desde o início — o diferencial é **agir**, não só monitorar (já existem players que só capturam publicações: Astrea, Projuris, Legal One, Digesto, Escavador)
- **Fundador:** técnico (vai construir), com **alguns contatos** no jurídico (acesso parcial a pilotos)

Como o repositório está vazio (greenfield, sem código), este plano é um **documento de produto + arquitetura + roteiro de construção**, não uma alteração de código existente.

---

## Recorte do produto (o fosso/moat)

O diferencial não é capturar publicações (commodity), e sim **executar o trabalho operacional de forma autônoma**: entrar no sistema do tribunal como o advogado, baixar a intimação, calcular o prazo, montar/minutar a petição e **protocolar** — com trilha de auditoria completa. Isso equivale ao "operar o portal como um humano" do Handle, aplicado a tribunais.

Espelhamos a arquitetura do Handle:
- **System of Record (SOR):** banco central que unifica processos, prazos, partes, andamentos e documentos de múltiplos tribunais.
- **Agentes verticais:** fluxos completos (cotação→aqui é "intimação→prazo→petição→protocolo").

---

## Restrições técnicas críticas (definem a arquitetura)

1. **Autenticação nos tribunais (o problema mais difícil).** PJe/e-SAJ exigem **certificado digital ICP-Brasil** ou login gov.br.
   - **A3** (token/cartão físico) — inviável de automatizar.
   - **A1** (arquivo `.pfx`) — pode ser carregado no contexto do navegador; exige o advogado subir o certificado + senha (sensível).
   - **Certificado em nuvem** (BirdID, VIDaaS, Certisign Cloud, SafeID) com **assinatura via API/push** — caminho mais limpo e seguro, padrão crescente no Brasil. **Recomendado** como via principal; A1 como alternativa.
2. **Captura via APIs oficiais antes de scraping.** Usar fontes oficiais sempre que possível, deixando "computer use" só para a **ação**:
   - **DJEN (Diário de Justiça Eletrônico Nacional / Comunica CNJ)** — fonte unificada de intimações/comunicações, com API. É a espinha dorsal da captura.
   - **DataJud (API Pública CNJ)** — metadados processuais e andamentos.
3. **Captchas e mudanças de layout.** PJe/e-SAJ têm captcha e mudam layout. Por isso a automação de **ação** combina conectores determinísticos (Playwright) + camada de visão/computer-use (Claude) como fallback, com **human-in-the-loop** quando travar.
4. **Responsabilidade profissional (OAB).** O advogado continua responsável. Ações irreversíveis (protocolar) devem passar, no início, por um **gate de aprovação humana** configurável — desligável conforme a confiança cresce. Isso atende à ambição de autonomia sem expor o cliente a malpractice. Auditoria imutável de tudo que o agente faz é obrigatória.

---

## Arquitetura recomendada

Padrão "SOR + conectores determinísticos + camada de agente (Claude)". Não usar computer-use puro em toda ação (lento/caro/frágil); usar fluxos determinísticos para o conhecido e Claude para raciocínio, normalização, minuta e exceções.

**Componentes (cada um com responsabilidade única, testável isoladamente):**

1. **System of Record (SOR)** — Postgres. Entidades: `escritorio`, `usuario`, `cliente`, `processo`, `intimacao/comunicacao`, `prazo`, `peticao`, `andamento`, `documento`, `credencial_assinatura`, `audit_log`.
2. **Captura (ingestion)** — serviço que consome **DJEN/Comunica** e **DataJud**, normaliza e grava intimações/andamentos no SOR. Roda em agenda (poll) por OAB/órgão.
3. **Motor de prazos (prazo engine)** — módulo **determinístico** (calendário forense, feriados nacionais/locais, suspensões, contagem em dias úteis CPC/CLT, recesso) que calcula data-limite. Claude entra só para **interpretar** o teor da intimação e classificar o tipo de prazo; o cálculo em si é código testável.
4. **Camada de agente (Claude Opus 4.8)** — orquestra o fluxo via tool use:
   - extrai e classifica o teor da intimação;
   - decide a peça cabível e gera a **minuta** da petição;
   - aciona o conector de protocolo;
   - usa **vision/computer-use** como fallback para navegação/layout novo.
   - Modelo: `claude-opus-4-8`, `thinking: {type: "adaptive"}`, `effort: "high"`. (Ver skill `claude-api` para detalhes de SDK.)
5. **Conectores de tribunal** — Playwright, um por sistema (começar por **um**). Sessão de navegador isolada por advogado com o certificado/assinatura. Fluxos: login → localizar processo → baixar intimação/autos → protocolar petição → confirmar.
6. **Cofre de credenciais/assinatura** — guarda referência ao certificado em nuvem / A1 cifrado. **Segredos nunca vão para prompt nem logs.** Assinatura via API do provedor de certificado em nuvem.
7. **Fila de jobs** — Celery/RQ + Redis (ou equivalente) para orquestrar capturas e ações assíncronas de longa duração.
8. **Gate de aprovação + auditoria** — antes de protocolar, item entra em fila de aprovação (configurável). Todo passo do agente é logado de forma imutável.
9. **Web app (frontend)** — Next.js/React. Telas: inbox de intimações, painel de prazos (com risco), fila de aprovação de petições, timeline/auditoria por processo, onboarding de certificado.

**Stack recomendada** (fundador técnico):
- **Backend/Agente:** Python (FastAPI) + SDK `anthropic` + Playwright (Python).
- **Dados:** PostgreSQL.
- **Fila/cache:** Redis + Celery/RQ.
- **Frontend:** Next.js (TypeScript) + React.
- **Infra:** containers; navegadores em workers isolados por tenant.

---

## Decomposição em sub-projetos

O escopo total é grande demais para um único ciclo. Ordem de construção:

1. **MVP — fatia vertical ponta a ponta (este plano detalha)**: 1 tribunal + 1 fluxo (intimação→prazo→minuta→protocolo com gate), para poucos pilotos.
2. Expansão de conectores (e-SAJ, Projudi, EPROC, demais TJs/TRTs).
3. Agentes adicionais (cobrança/financeiro, andamentos em massa, distribuição).
4. Multi-tenant/billing/escala e remoção progressiva do gate humano.

### Escopo do MVP (primeira fatia)

- **Um sistema só:** recomendado **PJe** (padrão CNJ, mais difundido em TRTs/TRFs e muitos TJs). Alternativa: **e-SAJ/TJSP** (maior mercado, sistema único e consistente) — decisão a confirmar com base nos pilotos disponíveis.
- **Captura:** via **DJEN/Comunica** (intimações) + **DataJud** (andamentos) — sem scraping na captura.
- **Prazo engine:** contagem em dias úteis + feriados + recesso para os tipos de prazo mais comuns do fluxo escolhido.
- **Minuta:** Claude gera rascunho de 1–2 tipos de peças comuns (ex.: manifestação simples / contestação-modelo) a partir de templates do escritório.
- **Protocolo:** conector Playwright + assinatura via certificado em nuvem, **com gate de aprovação humana obrigatório** nesta fase.
- **Auditoria + inbox + painel de prazos** no frontend.

---

## Arquivos/estrutura inicial a criar (greenfield)

```
/backend
  /sor            # modelos Postgres + migrations
  /capture        # clientes DJEN/Comunica + DataJud, normalização
  /prazo_engine   # cálculo determinístico de prazos (+ testes)
  /agent          # orquestração Claude (tool use), minuta de peças
  /connectors/pje # Playwright: login, localizar, baixar, protocolar
  /vault          # credenciais/assinatura (cifrado)
  /queue          # workers Celery/RQ
  /api            # FastAPI (endpoints p/ frontend)
/frontend         # Next.js: inbox, prazos, aprovação, auditoria
/infra            # docker-compose, workers de navegador
```

Reuso: SDK `anthropic` (ver skill `claude-api` — `client.messages.create` com tool use, `claude-opus-4-8`, adaptive thinking); Playwright para automação; bibliotecas de feriados nacionais (ex.: `workalendar`/`python-holidays`) como base do prazo engine.

---

## Como validar (o fundador tem alguns contatos no jurídico)

A validação é tão importante quanto o código:
1. **Entrevistas + pilotos** com 2–3 escritórios pequenos/médios dos seus contatos. Medir hoje: horas/mês gastas com prazos/protocolo e nº de quase-erros.
2. **Wizard-of-Oz inicial:** rodar o fluxo com captura real (DJEN/DataJud) + prazo engine automático, mas com humano executando o protocolo, enquanto o conector amadurece. Valida demanda e a contagem de prazos sem depender da parte mais frágil (computer-use).
3. **Critério de sucesso do MVP:** para os pilotos, capturar ≥90% das intimações relevantes, calcular o prazo correto em ≥99% dos casos testados, e gerar minutas aprovadas com edição mínima — com protocolo concluído via gate em produção.
4. **Verificação técnica:** testes unitários do prazo engine (casos de borda: recesso, feriado local, dias úteis); testes de integração dos clientes DJEN/DataJud com dados reais; teste ponta a ponta do conector PJe em ambiente de homologação/conta de teste antes de produção.

---

## Riscos principais

- **Certificado/assinatura** é o gargalo de viabilidade → priorizar certificado em nuvem com API; validar 1 provedor cedo.
- **Captcha/layout** no protocolo → manter fallback human-in-the-loop e computer-use; começar por 1 sistema.
- **Responsabilidade (OAB)** → gate de aprovação + auditoria imutável desde o dia 1.
- **Concorrência** (Astrea/Projuris/etc.) → o moat é a **execução autônoma**, não a captura; não competir em monitoramento puro.

---

## Próximo passo após aprovação

Transformar este plano no plano de implementação detalhado da **primeira fatia do MVP** (prazo engine + captura DJEN/DataJud primeiro, por serem as partes determinísticas e de maior valor imediato; conector PJe em seguida), via o fluxo de escrita de planos de implementação.
