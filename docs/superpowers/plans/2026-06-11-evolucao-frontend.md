# Plano — Evolução do Frontend Causor (sem novas APIs / sem auth)

**Escopo desta fase:** melhorar o que já existe e adicionar features que funcionam **contra os endpoints atuais** do backend. **Fora de escopo agora:** novos endpoints de API, autenticação, multi-tenant, conector de protocolo real.
**Data:** 11/06/2026.

---

## 1. Diagnóstico (o que está fraco hoje)

Tudo abaixo foi verificado em `frontend/app/page.tsx` (1944 linhas, um único arquivo) e `frontend/app/globals.css`.

### 1.1 Botões mortos (não fazem nada)
| Botão | Local | Estado |
|---|---|---|
| **Configurações** | sidebar, `page.tsx:596` | `NavItem` sem `onClick` — clica e nada acontece |
| **Ajuda** | sidebar, `page.tsx:595` | sem `onClick` |
| **Perfil/Conta** (avatar + chevron) | sidebar, `page.tsx:597` | sem `onClick`, sem menu |
| **Filtros** | viewbar, `page.tsx:773` | sem `onClick` |
| **Exportar** | viewbar, `page.tsx:777` | sem `onClick` |
| Itens de nav usam `href="#"` | `page.tsx:1862` | não há rota real; tudo é estado local |

### 1.2 Páginas parecidas demais entre si
- 7 das 10 views (`operacao`, `processos`, `intimacoes`, `prazos`, `calendario`, `peticoes`, `gate`) renderizam **o mesmo cabeçalho repetido**: `metricStrip` + `workflowStrip` + `viewbar` com os mesmos botões. Muda só a lista no meio.
- `peticoes` (`PeticoesView`) e `gate` (`GateOabView`) são **quase idênticas** — ambas mostram cards de petição com Aprovar/Protocolar.
- Não há **identidade visual por contexto**: inbox, prazos e processos poderiam ter layouts próprios, mas hoje compartilham a mesma "casca".

### 1.3 Conteúdo raso
- **Sem tela de detalhe.** Clicar num processo/intimação/prazo não abre nada — não há drill-down, timeline por processo, nem o `teor` completo da intimação.
- **Sem editor de minuta.** A petição só aparece como texto (`peticao.conteudo`); não dá para editar antes de aprovar.
- **Edição de prazo via `window.prompt`** (`page.tsx:266`) — UX crua, sem validação visual.
- **Métricas inventadas:** `hoursReturned` e `automationRate` são heurísticas fixas (`page.tsx:292-293`), não dados reais — passam impressão falsa.
- **Sem página de Configurações, Ajuda ou Perfil.**
- **Calendário** é só um trilho de 14 dias (`page.tsx:1411`), sem visão de mês.

### 1.4 Dívida estrutural
- **Um único arquivo de 1944 linhas** com ~15 componentes. Difícil evoluir; qualquer feature nova engrossa o monólito.
- CSS num único `globals.css` gigante.

---

## 2. Princípios de design para esta fase

1. **Cada página tem um trabalho.** Layout e ações específicas do contexto, não a mesma casca repetida.
2. **Nenhum botão mente.** Ou funciona, ou não existe, ou está claramente "em breve".
3. **Profundidade por drill-down.** Toda lista leva a um detalhe útil.
4. **Honestidade de dados.** Métrica que não é real sai (ou vira claramente "estimativa").
5. **Trabalhar com o backend que existe.** Nenhuma feature deste plano exige endpoint novo.

---

## 3. Plano por fases

### Fase A — Tapar buracos e tornar tudo honesto (rápido, alto impacto)
Objetivo: nada quebrado, nada que mente. Base para o resto.

- **A1. Modular o monólito.** Quebrar `page.tsx` em `components/` e `views/` (um arquivo por view + componentes compartilhados). Pré-requisito para evoluir sem dor.
- **A2. Página de Configurações (funcional, local).** Tela real ligada ao botão. Sem backend novo: persistir em `localStorage` — tema (claro/escuro), OAB/UF padrão da captura, anos do calendário forense, limiar de confiança para destacar minuta, preferências de exibição. Ligar `page.tsx:596`.
- **A3. Menu de Perfil e Ajuda.** Dropdown no perfil (placeholder honesto: conta atual, "sair" desabilitado com tooltip "em breve"). "Ajuda" abre painel com atalhos, status dos conectores e link para a doc local.
- **A4. Botão Filtros funcional.** Abrir um painel de filtros real por view (tribunal, sistema, risco, status, intervalo de datas) — opera sobre os dados já carregados.
- **A5. Botão Exportar funcional.** Exportar a lista corrente para CSV no cliente (sem backend). Começa por prazos e auditoria.
- **A6. Remover/realinhar métricas falsas.** Tirar `hoursReturned`/`automationRate` heurísticos ou rotulá-los honestamente como estimativa; trocar por métricas reais derivadas do SOR (ex.: % de prazos em dia, intimações sem minuta).

### Fase B — Diferenciar as páginas e dar profundidade
Objetivo: cada tela ganha cara e utilidade próprias.

- **B1. Tela de detalhe do Processo.** Drill-down: dados do processo + timeline (andamentos via `GET /audit`/dados já carregados) + intimações + prazos + minutas vinculadas, num só lugar.
- **B2. Detalhe da Intimação (drawer).** Abrir o `teor` completo, metadados e ação "gerar minuta" inline — hoje o teor aparece truncado na lista.
- **B3. Editor de minuta.** Tela/drawer para **ver e editar** o conteúdo da petição antes de aprovar (usa o conteúdo existente; salvar local até existir endpoint de update). Mostra a classificação da IA (tipo, confiança) ao lado.
- **B4. Unificar Minutas × Gate OAB.** Decidir: ou viram uma só página com abas (Rascunho → Aprovada → Protocolada), ou cada uma ganha papel distinto (Minutas = redação/edição; Gate = só aprovação/risco). Eliminar a duplicação atual.
- **B5. Editor de prazo decente.** Trocar o `window.prompt` por um modal com date picker, validação e nota de revisão (a nota já é aceita pelo `PATCH /prazos`).
- **B6. Calendário de verdade.** Visão mensal além do trilho de 14 dias, com concentração de risco por dia e clique para o prazo.

### Fase C — Novas features (ainda sem API nova)
Objetivo: valor visível que diferencia do "monitorador".

- **C1. Worklist "Hoje" priorizada.** Fila única ordenada por risco × esforço — o "inbox zero" jurídico. Reaproveita `reviewQueue`.
- **C2. Simulador de prazo.** Ferramenta onde o usuário digita data de publicação + dias + dias úteis e vê a contagem **explicada**. (Cálculo no front por ora; depois pluga no `prazo_engine`.)
- **C3. Painel de risco/ROI honesto.** Dashboard com números reais: prazos por faixa de risco, vencidos, % cumpridos no prazo, intimações sem minuta, idade média da fila.
- **C4. Notificações in-app.** Centro de avisos derivado dos dados (prazos D-3/D-1/vencidos, minutas paradas) — sem push externo, só sino + lista.
- **C5. Busca global (command palette).** Ctrl/Cmd-K para saltar a processo, intimação, prazo ou view.
- **C6. Tema claro/escuro + densidade.** Ligado às Configurações (A2).

### Fase D — Polimento
- **D1. Estados vazios úteis** (cada empty com próxima ação sugerida, não só "nada encontrado").
- **D2. Skeletons de carregamento** no lugar de telas em branco.
- **D3. Acessibilidade** (foco, aria, navegação por teclado nos modais/drawers).
- **D4. Responsividade** para telas menores.

---

## 3.1 Status de execução

- **Fase A — concluída** (11/06): dark mode + Configurações (`localStorage`), Ajuda, Perfil, Filtros, Exportar CSV, métricas honestas. A1 (modularização) **parcial** — extraídos `lib/settings.ts`, `lib/export.ts`, `lib/drafts.ts`, `app/SettingsModal.tsx`; `page.tsx` ainda grande.
- **Fase B — concluída exceto B6** (11/06): B1 detalhe de processo + B2 detalhe de intimação (drawer `DetailDrawer.tsx`), B3 editor de minuta local (`MinutaEditor.tsx`, edição em `localStorage`, rotulada), B4 Minutas (board de redação) × Gate (lanes) com papéis distintos, B5 modal de revisão de prazo (`PrazoEditModal.tsx`, substitui `window.prompt`). **B6 (calendário mensal) pendente.**
- Validação: `npx tsc --noEmit` exit 0; dev server compila limpo; GET / 200. Screenshot não feito (sem ferramenta de browser no ambiente).

---

## 4. Ordem sugerida de execução

1. **A1** (modularizar) — destrava tudo.
2. **A2–A6** (botões honestos + Configurações) — resolve a reclamação direta dos "botões que não funcionam".
3. **B4 + B1 + B2 + B3** (diferenciar páginas + profundidade) — resolve "páginas parecidas / pouca coisa".
4. **C1–C3** (worklist, simulador, risco real) — adiciona valor novo.
5. **B5, B6, C4–C6, D\*** — refinamento.

> Cada item é entregável e testável isoladamente. Sugiro fechar a Fase A antes de abrir a B.

---

## 5. Como validar cada entrega

- App roda (`pnpm dev` + backend em :8000) e a tela alvo funciona com dados reais de captura.
- `pnpm build` / typecheck sem erros.
- Nenhum botão visível sem ação.
- A view alterada tem layout distinto das demais (critério do "não parecer igual").

---

## 6. Decisões tomadas (11/06/2026)

1. **Prioridade:** **Fase A primeiro** — modularização + botões honestos + Configurações.
2. **Minutas × Gate (B4):** **manter as duas com papéis distintos** — Minutas = redigir/editar; Gate OAB = aprovação e risco.
3. **Dark mode:** **entra agora**, na Fase A, ligado à tela de Configurações.
4. **Configurações (A2):** persistência em `localStorage` nesta fase (sem backend novo).
