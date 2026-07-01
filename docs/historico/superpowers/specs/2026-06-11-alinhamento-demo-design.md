# Design: Alinhamento do software à landing page (demo-ready)

**Data:** 2026-06-11
**Status:** Aprovado pelo usuário
**Contexto:** O produto não está em produção. A landing page (`causor-landing/index.html`) promete o ciclo completo capturar → calcular prazo → minutar → aprovar → protocolar → auditar. O software cobre captura, prazo, minuta, gate e auditoria, mas o protocolo é simulado, a UI não compartilha identidade visual com a landing e o app abre vazio (sem dados). Decisão: alinhar o software à landing **antes** de integrar APIs reais de tribunal (conector PJe, assinatura em nuvem real ficam para depois).

## Objetivo

Ao final desta fase, o app local conta a história completa da landing com dados vivos, visual unificado e sem features órfãs. Tudo que é simulado fica explicitamente rotulado como simulado.

**Uso-alvo:** demo para pilotos/investidores (decidido pelo usuário). O caminho de captura real (DJEN/DataJud) permanece funcional, mas a prioridade é a demo.

## Decisões do usuário

- Uso principal: demo para pilotos/investidores.
- Identidade visual: unificar o app com a landing (Satoshi/Inter/JetBrains Mono, cream, verde, pills, badges mono).
- Features a adicionar: Fila do dia, Protocolo simulado ponta a ponta, Radar de Prazo (alertas in-app D-3/D-1/D-0), Onboarding de certificado (vault).
- Cortes: dark mode, Calendário Forense, edição local de minuta via localStorage (substituída por persistência real no backend).
- Ordem de ataque: "história primeiro" — seed → cortes → refactor → visual → features → polimento.

## Etapas

### Etapa 0 — Seed de demo (backend)

Novo comando CLI: `python -m app.cli seed-demo`.

- Idempotente (re-rodável sem duplicar dados; estratégia: marcador determinístico, ex. escritório com nome fixo de demo — se existe, recriar/atualizar em vez de duplicar).
- Cria: 1 escritório, 2+ usuários (advogado responsável e apoio), ~10 processos com números CNJ verossímeis (formato NNNNNNN-DD.AAAA.J.TR.OOOO), varas/classes/tribunais variados.
- Intimações com teor realista em PT-BR: citação, intimação de sentença, despacho de perícia, intimação de pagamento etc.
- Prazos cobrindo todos os estados visuais: vencido, vence em 1 dia (alto risco), vence em 3 dias (médio), confortável (baixo).
- Minutas em todas as fases: rascunho, em revisão, aprovada (aguardando protocolo), protocolada com comprovante simulado.
- Trilha de auditoria coerente com os eventos acima.
- Credencial de assinatura de exemplo cadastrada via vault.
- Os estados reproduzem o print do hero da landing: Contestação D-1, Manifestação D-3, Embargos com minuta pronta aguardando aprovação, Réplica protocolada com comprovante.

### Etapa 1 — Cortes

- Remover dark mode: toggle no Settings, classe/tema e CSS associado. Tema claro único.
- Remover Calendário Forense: view, item de navegação e CSS associado.
- Substituir edição local (localStorage) do MinutaEditor por persistência real:
  - `PATCH /peticoes/{id}` — atualiza `conteudo` e permite transição de status (ex.: rascunho → em_revisao). Gera evento de auditoria.
  - Regra: petição protocolada não pode ser editada (HTTP 409).
  - Remover `lib/drafts.ts` e o aviso "edição local".

### Etapa 2 — Fatiar o page.tsx (refactor sem mudança de comportamento)

- `frontend/app/page.tsx` (2.318 linhas) é quebrado em:
  - `app/views/` — uma view por tela (Central, FilaDoDia, Intimacoes, Prazos, Processos, Minutas, GateOAB, Auditoria).
  - `app/components/` — componentes compartilhados (badges de risco, cards, métricas, painéis; DetailDrawer e modais já existem como arquivos próprios).
  - `lib/` — hooks de dados/estado compartilhado.
- Critério de aceitação: comportamento idêntico, `tsc` verde antes e depois, dev server sem erros.

### Etapa 3 — Identidade visual da landing

- Tokens em `globals.css` espelhando a landing: `--cream #f8f7f5`, `--green #166534`, `--green-bg #f0fdf4`, `--red #fb2c36`, `--amber #b45309`, bordas `#e5e5e5`.
- Tipografia: Satoshi (títulos), Inter (corpo), JetBrains Mono (badges, números de processo, contadores).
- Botões pill (border-radius 999px), badges de risco idênticas às da landing ("VENCE EM 1 DIA" vermelho, "VENCE EM 3 DIAS" âmbar, "MINUTA PRONTA · AGUARDA APROVAÇÃO" / "PROTOCOLADA · COMPROVANTE OK" verde).
- Estados vazios desenhados (hoje a tela zerada parece produto morto).

### Etapa 4 — Features novas

**Fila do dia** (tela inicial, "⚡ Fila do dia" como no print da landing):
- Lista única priorizada por risco × proximidade do vencimento.
- Cada item mostra: peça cabível, processo, badge de risco, e a ação principal do estado atual (revisar minuta, aprovar, protocolar).
- Substitui a "Central de Comando" como view default (a Central pode permanecer como visão executiva secundária).

**Protocolo simulado ponta a ponta:**
- `POST /peticoes/{id}/protocolar` — chama `app/queue/jobs.run_fake_protocol_job` (já existente; exige status `aprovada`, senão 409).
- UI: no Gate OAB, após aprovar, aparece a ação "Protocolar"; ao concluir, mostra comprovante (referência do protocolo) e os eventos na Auditoria.
- Rótulo honesto visível: "simulado — conector PJe em desenvolvimento".

**Radar de Prazo (alertas in-app):**
- `GET /alertas` — derivado dos prazos (sem tabela nova): D-3, D-1, D-0 e vencidos, com nível de escalonamento.
- UI: sino de notificações no topo; contagem e lista com link para o prazo. Estado "lido" persiste apenas no navegador (localStorage) — simplificação consciente de MVP.

**Onboarding de certificado (vault):**
- Endpoints sobre `app/vault/service.py` existente: cadastrar (`POST /credenciais`), listar (`GET /credenciais`), desativar (`PATCH /credenciais/{id}`).
- UI em Configurações: escolher provedor (BirdID/VIDaaS/SafeID), informar referência externa; lista de credenciais com desativação.
- Nunca armazena segredo — apenas referência; o texto da UI explica isso (história de segurança da landing).

### Etapa 5 — Verificação e polimento

- Backend: TDD nos endpoints novos (`PATCH /peticoes`, `POST /peticoes/{id}/protocolar`, `GET /alertas`, endpoints de vault, seed) — pytest + ruff verdes.
- Frontend: `tsc` verde, smoke manual nas telas com a seed carregada.
- Passada visual final comparando lado a lado com a landing (print do hero).

## Tratamento de erros

- API offline → banner existente de "API indisponível" permanece.
- Protocolo sem aprovação → 409 com mensagem clara (já implementado no job; expor na API).
- Edição de petição protocolada → 409.
- Seed re-rodada → não duplica dados.

## Fora de escopo (explícito)

- Conector PJe real / Playwright / Computer Use.
- Integração real com provedores de assinatura (BirdID etc.).
- E-mail/WhatsApp no Radar de Prazo.
- Importação Excel/CSV.
- Multi-tenant, billing, produção.

## Riscos

- **Etapa 2 (fatiamento)** é a de maior risco — mitigada por ser refactor puro com `tsc` como rede de segurança e sem mudança de comportamento.
- Radar sem "lido" no servidor: aceito como simplificação de MVP.
- Fontes da landing (Satoshi via Fontshare) dependem de rede; fallback `system-ui` definido no CSS.
