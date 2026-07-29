# UX mobile do Causor — design aprovado

Data: 2026-07-28
Status: aprovado pelo usuário (brainstorming concluído)

## Objetivo

Tornar o app do Causor (`frontend/`, Next.js App Router) usável e agradável no
celular. Hoje o layout é um grid fixo desktop-only (`.shell` =
`220px minmax(0,1fr)`) cuja sidebar de 220px nunca colapsa: num celular ela come
metade da tela, as tabelas densas estouram na horizontal e os modais foram
desenhados para telas largas. Nenhum comportamento de negócio, rota, dado ou
endpoint muda — o trabalho é **exclusivamente de apresentação** (CSS + um
componente de navegação novo + o `viewport` do layout).

### Decisões fechadas com o usuário (não re-litigar)

1. **Prioridade de uso no celular**: "acompanhar e agir rápido" — prazos
   urgentes, ler intimações, aprovar/protocolar minutas e usar o Assistente. As
   views de tabela densa (Processos) são secundárias: só precisam **não
   quebrar**, não serão redesenhadas nesta rodada.
2. **Navegação**: **bottom nav fixa** (padrão de app nativo, alcance do polegar)
   + top bar enxuta. A sidebar de 220px é substituída no celular, não adaptada.
3. **Profundidade**: **polir as telas prioritárias de verdade** — não é só um
   corretivo responsivo. As views de "agir rápido" viram cards mobile; os
   modais viram bottom-sheets; touch targets e safe-area entram.

## Escopo

**Dentro do escopo** (redesenhado como mobile de verdade):

- Navegação: sidebar → top bar + bottom nav + sheet "Mais".
- Views prioritárias: Fila do dia (dashboard worklist), Prazos, Intimações,
  Minutas (Petições), Gate OAB.
- Modais/overlays: modal genérico (`.modalCard`), Captura por OAB, DetailDrawer,
  MinutaEditor, SettingsModal, painel de Filtros, confirmações.
- Telas de entrada: login e set-password (passada de responsivo).
- Fundação: `viewport`, safe-area, touch targets, no-zoom nos inputs.

**Fora do escopo** (só "não quebrar" via scroll horizontal contido):

- Processos, Templates, Protocolos, Conectores, Auditoria, Onboarding,
  Assistant workspace (redesenho profundo) — reflui e não quebra, sem redesenho
  card-a-card. Podem entrar numa segunda passada.

## Abordagem técnica

Breakpoint mobile único: **`max-width: 640px`**. O app já usa media queries em
680/820/880/1080px para ajustes desktop/tablet; 640px passa a ser o "modo
celular" onde a estrutura muda de fato. Tablet mantém o comportamento atual.

Onde o CSS não alcança sozinho (a árvore da navegação precisa de um novo nó e de
estado), entra **um componente React novo** e um pequeno estado no `page.tsx`.
Todo o resto é CSS em `frontend/app/globals.css`.

## 1. Fundação responsiva

### 1.1 `viewport` no `frontend/app/layout.tsx`

Adicionar o export `viewport` do Next:

```ts
export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" }
  ],
  viewportFit: "cover" // habilita env(safe-area-inset-*) no notch/barra inferior
};
```

### 1.2 Tokens de mobile (`globals.css`)

- Alvos de toque ≥44px no `≤640px` para `.toolbarButton`, `.navItem`,
  `.statusTab`, `.dismiss-notice` e ações de card.
- Inputs com `font-size: 16px` no `≤640px` (`.modalCard input`, `.search input`,
  campos de login) para impedir o zoom automático do iOS ao focar.
- Variável de conveniência para a altura da bottom nav
  (`--mobile-nav-h: 60px`) usada no padding inferior do conteúdo e nas
  safe-areas.

## 2. Navegação mobile

### 2.1 Shell (`globals.css`, `≤640px`)

- `.shell` e `.shell.sidebarCollapsed` → `grid-template-columns: 1fr` (coluna
  única). `.assistantShell` idem.
- `.sidebar` → `display: none` no celular (a navegação migra para top bar +
  bottom nav). O estado `sidebarCollapsed` do desktop fica inerte no mobile.
- `.workspace` ganha `padding-bottom: calc(var(--mobile-nav-h) +
  env(safe-area-inset-bottom))` para o conteúdo não ficar sob a bottom nav.
- `.appbar` (já `position: sticky`) vira a top bar: no `≤640px` mostra a marca à
  esquerda (hoje ela vive na sidebar) + ações à direita (tema, `RadarBell`,
  Captura por OAB). Os crumbs "Legal Ops › {view}" encolhem para só o título da
  view.

### 2.2 Componente novo `MobileNav` (`frontend/app/components/MobileNav.tsx`)

- Renderizado em `page.tsx` apenas como barra fixa no rodapé (a visibilidade
  desktop/mobile é controlada por CSS: `display: none` acima de 640px).
- `position: fixed; bottom: 0`, full-width, `padding-bottom:
  env(safe-area-inset-bottom)`, borda superior hairline, fundo `var(--sidebar)`.
- **5 itens fixos**: `Início` (dashboard), `Prazos`, `Intimações`, `Minutas`
  (peticoes), `Mais (⋯)`. Ícones reaproveitados do lucide já importado
  (HomeIcon, Clock3, Inbox, FilePenLine, e um "mais"/menu). Item ativo espelha o
  `view` atual (mesma fonte de verdade `ViewKey` do `page.tsx`); onClick chama
  `setView`.
- Recebe `view`, `onNavigate(view)` e `onOpenMore()` por props — sem estado
  próprio de navegação além do sheet "Mais".

### 2.3 Sheet "Mais"

- Reusa o padrão de bottom-sheet da seção 3. Lista os destinos restantes, com o
  **Assistente em destaque no topo** (é tarefa prioritária mas não coube nos 5
  fixos): Assistente, Gate OAB, Processos, Templates, Protocolos, Conectores,
  Auditoria, Onboarding, e as ações de rodapé da sidebar (Ajuda, Configurações,
  Conta). Selecionar um item fecha o sheet e navega/abre o overlay
  correspondente.
- Estado: um booleano em `page.tsx` (`mobileMoreOpen`), análogo aos outros
  overlays já existentes.

## 3. Views prioritárias → cards mobile

As views de "agir rápido" usam a estrutura `.dataTable` (um `.dataHead` de
cabeçalho + `.dataRow` como grid CSS): **Fila do dia** (`.filaTable`),
**Prazos** (`.deadlineTable`), **Intimações** (`.inboxTable`), **Minutas** e
**Gate** (tabelas de petição). No `≤640px`:

- `.dataHead` → `display: none` (o cabeçalho de colunas não faz sentido
  empilhado).
- `.dataRow` → deixa de ser grid horizontal e vira **card empilhado**
  (`display: flex; flex-direction: column`), com borda hairline e espaçamento
  confortável: bloco de data/risco (`.filaDate`) no topo, título da peça,
  número do processo em `mono`, badge de status (`.dayBadge`/`DeadlineBadge`),
  e as ações (`.dataRowEnd`) como **botões full-width** empilhados (ou lado a
  lado quando couberem), com altura de toque ≥44px.
- `.statusTabs` do dashboard → **scroll horizontal** com `overflow-x: auto` e
  `scroll-snap`, sem quebrar linha; mantém contagem por aba.
- `.viewbar` (título + busca + Filtros + Exportar) → empilha em coluna; a
  `.search` fica full-width; Filtros/Exportar viram uma linha de botões abaixo.
- O painel `FiltersPanel` abre como bottom-sheet (seção 4), não como popover
  ancorado.

Reaproveitar as classes de risco/tom já existentes (`.filaDate.risk/.warn/.done`,
`.dayBadge.*`) — a cor semântica não muda, só o arranjo.

### Tabelões secundários

`.processTable` (Processos) e demais tabelas fora do escopo: envolver o
`.dataTable` num container com `overflow-x: auto` e um piso de largura mínima,
para rolarem na horizontal sem estourar o layout nem a bottom nav. Sem
conversão para cards nesta rodada.

## 4. Modais → bottom sheets

No `≤640px`, todo overlay centrado vira **folha que sobe do rodapé**:

- `.modalOverlay` → `align-items: flex-end` (cola no rodapé).
- `.modalCard` → `width: 100%`, `max-width: none`, cantos superiores
  arredondados (`border-radius: 16px 16px 0 0`), `max-height: 90dvh` com
  `overflow-y: auto`, `padding-bottom: calc(20px + env(safe-area-inset-bottom))`.
- `.modalActions` → botões full-width (empilhados) para toque fácil.
- Animação de entrada (slide-up) respeitando `prefers-reduced-motion` (a media
  query já existe em `globals.css`).

Mesmo tratamento para os overlays que não usam `.modalCard` diretamente:

- **DetailDrawer** (`frontend/app/DetailDrawer.tsx`): o drawer lateral vira
  sheet inferior (ou full-screen) no celular.
- **MinutaEditor** (`frontend/app/MinutaEditor.tsx`): editor em tela cheia no
  celular (área de texto ocupa a altura útil, ações fixas no rodapé com
  safe-area).
- **SettingsModal** (`frontend/app/SettingsModal.tsx`): sheet/tela cheia com as
  abas roláveis.

O foco/trap de teclado e o `role="dialog"` existentes permanecem — só muda a
apresentação.

## 5. Telas de entrada

Passada de responsivo em `frontend/app/login/page.tsx` e
`frontend/app/set-password/page.tsx`: largura do card `min(420px, 100% - 32px)`,
padding reduzido no celular, botões full-width, inputs `font-size: 16px`. É a
primeira tela do produto e precisa abrir bem no telefone.

## Componentização e responsabilidade

- `MobileNav` tem responsabilidade única (renderizar a barra e delegar navegação
  por props); não guarda estado de dados nem conhece a lógica das views.
- O sheet "Mais" e os bottom-sheets reusam o mesmo padrão de overlay — sem
  duplicar markup de sheet por tela.
- `page.tsx` continua sendo o dono do `view`/overlays; a mudança nele se limita
  a: renderizar `<MobileNav>`, o estado `mobileMoreOpen`, e a marca na `.appbar`
  para o celular. Sem novos caminhos de dados.

## Testes e verificação

- **`vitest`** para qualquer lógica nova de UI (ex.: item ativo do `MobileNav`
  derivado do `view`, abertura/fechamento do sheet "Mais"). Segue o padrão dos
  testes já existentes em `frontend/app/components/*.test.tsx`.
- **`pnpm check`** (lint + typecheck + test) verde antes de concluir.
- **Verificação visual no app real** com o skill `verify` (rede 100%
  interceptada, sem tocar Supabase/API reais) em viewport de celular
  (~390×844), percorrendo: navegação (bottom nav + "Mais"), Fila do dia,
  Prazos, Intimações, um modal (Captura por OAB) e o login. Nenhum overflow
  horizontal; alvos de toque confortáveis; safe-area respeitada.

## Riscos e mitigações

- **Regressão no desktop**: todas as mudanças estruturais ficam atrás de
  `@media (max-width: 640px)`; o `MobileNav` some via CSS acima de 640px. O
  desktop não deve mudar — confirmar no `verify` em viewport largo também.
- **Duplicação de navegação** (sidebar + bottom nav): a sidebar é `display:
  none` no mobile e a bottom nav é `display: none` no desktop; nunca coexistem.
- **`100dvh` e barras do navegador móvel**: já usamos `dvh` no `.shell`/
  `.sidebar`; manter `dvh` nos sheets e no padding de conteúdo.
