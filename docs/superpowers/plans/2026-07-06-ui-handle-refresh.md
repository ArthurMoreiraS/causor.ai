# Reforma visual "Causor × Handle" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reestilizar o app Causor inteiro na linguagem visual do Handle.ai (branco puro, hairlines, tipografia display + mono caps, paleta monocromática com cor apenas semântica), sem mudar nenhum comportamento.

**Architecture:** O app é 100% token-driven (`frontend/app/globals.css`, ~5.600 linhas, CSS vars consumidas por todas as views). Etapa 1 reescreve os tokens (efeito global imediato nos 2 temas); as etapas seguintes fazem cirurgia pontual: controles, badges, shell, hero da home com statRow, títulos display por view e conversão das listas em tabelas hairline via um padrão novo `.dataTable`.

**Tech Stack:** Next.js 15 + React 19 + CSS puro (globals.css). Sem libs novas. Fontes: Inter + JetBrains Mono (next/font, já configuradas).

**Spec:** `docs/superpowers/specs/2026-07-05-ui-handle-refresh-design.md` (aprovado — decisões de cor/escopo/tema/tipografia já fechadas; não re-litigar).

## Global Constraints

- **Zero mudança de comportamento**: rotas, dados, chamadas de API, handlers, textos funcionais, roles/aria e paginação ficam como estão. Só apresentação.
- **Dois temas sempre**: toda mudança precisa funcionar em claro e escuro (`[data-theme="dark"]`).
- **Monocromático**: `--accent` vira preto/branco; vermelho = risco/vencido, âmbar = vence ≤3d, verde = cumprido/ativo. Nenhuma outra cor.
- **Micro-labels**: JetBrains Mono, maiúsculas, 9.5–11px, `letter-spacing: 0.08em+`, cor `--muted`/`--muted-2`.
- **Sem sombras** exceto overlays (modal, drawer, dropdown, toast).
- **Comandos** (rodar em `/frontend`): `pnpm typecheck` · `pnpm lint` · `pnpm test` · `pnpm build` · `pnpm dev`.
- **Commits frequentes**: um por task, mensagem em português, prefixo `ui:`.
- A landing page (`causor-landing`) está fora do escopo.

---

### Task 1: Tokens dos dois temas

**Files:**
- Modify: `frontend/app/globals.css:1-78` (blocos `:root` e `[data-theme="dark"]`)

**Interfaces:**
- Produces: os valores de token que TODAS as tasks seguintes assumem — em especial `--radius-xs: 4px`, `--radius-sm: 6px`, `--radius-md: 8px`, `--radius-lg: 8px`, `--radius-xl: 10px`, `--accent` preto/branco, `--shadow-sm: none`.

- [ ] **Step 1: Substituir o bloco `:root` (linhas 2–43) por:**

```css
:root {
  --bg: #ffffff;
  --panel: #ffffff;
  --panel-soft: #fafafa;
  --sidebar: #fcfcfc;
  --ink: #111111;
  --ink-soft: #404040;
  --muted: #737373;
  --muted-2: #a3a3a3;
  --line: #ececec;
  --line-strong: #d4d4d4;
  --chip: #f5f5f5;
  --accent: #111111;
  --accent-bg: #f5f5f5;
  --accent-border: #e0e0e0;
  --solid: #111111;
  --warn: #b45309; /* âmbar — vence em ≤3 dias */
  --warn-bg: #fffbeb;
  --risk: #fb2c36; /* vermelho — vencido/risco */
  --risk-bg: #fef2f2;
  --ok: #166534;
  --ok-bg: #f0fdf4;
  --success: #166534;
  --success-bg: #f0fdf4;
  --shadow: rgba(0, 0, 0, 0.06);
  /* Escala de raio Handle: cantos retos — badges 4, controles 6, cards 8. */
  --radius-xs: 4px;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 8px;
  --radius-xl: 10px;
  --radius-pill: 999px;
  /* Sombras só em overlays (modal/dropdown/toast); superfícies são flat. */
  --shadow-sm: none;
  --shadow-md: 0 8px 22px -16px rgb(0 0 0 / 18%);
  --shadow-lg: 0 24px 60px -24px rgb(0 0 0 / 16%);
  --font-title: var(--font-inter, "Inter"), ui-sans-serif, system-ui, -apple-system,
    BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: var(--font-jbmono, "JetBrains Mono"), ui-monospace, SFMono-Regular, Menlo,
    Consolas, monospace;
  color-scheme: light;
}
```

- [ ] **Step 2: Substituir o bloco `[data-theme="dark"]` (linhas 49–78) por:**

```css
[data-theme="dark"] {
  color-scheme: dark;
  --bg: #0a0a0a;
  --panel: #111113;
  --panel-soft: #17171a;
  --sidebar: #0d0d0f;
  --ink: #f5f5f5;
  --ink-soft: #d4d4d4;
  --muted: #a3a3a3;
  --muted-2: #6b6b70;
  --line: #232326;
  --line-strong: #3a3a3f;
  --chip: #1c1c1f;
  --accent: #f5f5f5;
  --accent-bg: #1c1c1f;
  --accent-border: #2e2e33;
  --solid: #f5f5f5;
  --warn: #fbbf24;
  --warn-bg: #251d0a;
  --risk: #f87171;
  --risk-bg: #2a1517;
  --ok: #4ade80;
  --ok-bg: #10251a;
  --success: #4ade80;
  --success-bg: #10251a;
  --shadow: rgba(0, 0, 0, 0.5);
  --shadow-sm: none;
  --shadow-md: 0 8px 22px -16px rgb(0 0 0 / 55%);
  --shadow-lg: 0 24px 60px -24px rgb(0 0 0 / 60%);
}
```

Não tocar nos overrides `[data-theme="dark"] .notice`, `.queueStatus` etc. (linhas 80–126): continuam corretos com os novos tokens.

- [ ] **Step 3: Verificar**

Run: `pnpm typecheck` — Expected: PASS (CSS não afeta, é sanity check).
Run: `pnpm dev` e abrir http://localhost:3000 — Expected: canvas branco, teal sumiu (itens ativos/ícones agora pretos), cards ainda com raio antigo em alguns literais (esperado — tasks seguintes). Alternar tema escuro nas configurações e conferir contraste.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/globals.css
git commit -m "ui: tokens monocromáticos Handle nos temas claro e escuro"
```

---

### Task 2: Controles — botões, inputs, busca, foco, auth

**Files:**
- Modify: `frontend/app/globals.css` (seletores indicados)

**Interfaces:**
- Consumes: tokens da Task 1.
- Produces: `.toolbarButton`/`.toolbarButton.primary` retangulares 6px que todas as views já usam (nenhuma mudança de classe em JSX é necessária).

- [ ] **Step 1: Aplicar as edições pontuais abaixo (buscar pelo seletor):**

1. `.toolbarButton, .iconButton` (linha ~549): remover a linha `box-shadow: var(--shadow-sm);` (agora é `none` de qualquer forma; limpar a declaração).
2. `.search` (linha ~1438): trocar `border-radius: 999px;` por `border-radius: var(--radius-sm);`.
3. `.searchSelectControl` (linha ~3104): substituir as declarações `border`, `background` e `box-shadow` por:

```css
  border: 1px solid var(--line);
  background: var(--panel);
  box-shadow: none;
```

4. `.searchSelectControl:focus-within, .searchSelect.open .searchSelectControl` (linha ~3118): substituir o `box-shadow` composto por `box-shadow: none;` (o realce fica só na borda).
5. `.authButton` (linha ~5026): trocar `border-radius: 999px;` por `border-radius: var(--radius-md);`.
6. `.authCard` (linha ~4963): trocar `border-radius: 16px;` por `border-radius: var(--radius-xl);` e `box-shadow: 0 24px 60px -24px rgba(0, 0, 0, 0.14);` por `box-shadow: var(--shadow-lg);`.
7. Media query `max-width: 1080px`, regra `.sideNav a, .sideNav .navItem, ...` (linha ~2747): trocar `border-radius: var(--radius-pill);` por `border-radius: var(--radius-sm);`.

- [ ] **Step 2: Verificar**

Run: `pnpm dev` — Expected: botões e busca retangulares (6px), botão primário preto (claro) / branco (escuro), login com card 10px e botão retangular.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/globals.css
git commit -m "ui: controles retangulares e flat (botões, busca, inputs, auth)"
```

---

### Task 3: Badges e linguagem de status

**Files:**
- Modify: `frontend/app/globals.css` (seletores indicados)

**Interfaces:**
- Produces: badges mono caps 4px (`.dayBadge`, `.pill`, `.jobStatus`, `.queueStatus`, `.connector small`, `.cycleHealth`) usados como estão pelas views — sem mudança de JSX.

- [ ] **Step 1: Substituir o bloco `.dayBadge[class]` (linha ~1498) por:**

```css
.dayBadge[class] {
  justify-self: center;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 22px;
  max-width: 100%;
  padding: 0 8px;
  border: 0;
  border-radius: var(--radius-xs);
  background: var(--chip);
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  line-height: 1;
  text-align: center;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  white-space: nowrap;
}
```

E as variantes (substituir os blocos `.dayBadge.neutral/.today/.risk/.done` existentes):

```css
.dayBadge.neutral {
  color: var(--muted);
  background: var(--chip);
}

.dayBadge.today {
  color: var(--warn);
  background: var(--warn-bg);
}

.dayBadge.risk {
  color: var(--risk);
  background: var(--risk-bg);
  box-shadow: none;
}

.dayBadge.done {
  color: var(--ok);
  background: var(--ok-bg);
}
```

Manter o `.dayBadge::before` (dot) como está.

- [ ] **Step 2: Edições pontuais nos demais badges:**

1. `.pill[class]` (linha ~1908): trocar `border-radius: var(--radius-pill);` por `border-radius: var(--radius-xs);`, `font-weight: 500` por `font-weight: 600` e `letter-spacing: 0.05em` por `letter-spacing: 0.08em`.
2. `.jobStatus` (linha ~4692): trocar `border-radius: 999px;` por `border-radius: var(--radius-xs);` e `letter-spacing: 0.04em` por `letter-spacing: 0.08em`.
3. `.queueStatus` (linha ~1461): trocar `letter-spacing: 0.05em` por `letter-spacing: 0.08em`.
4. Substituir o bloco `.connector small` (linha ~1864) por (dot verde estilo "● LIVE"):

```css
.connector small {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 22px;
  padding: 0 8px;
  border-radius: var(--radius-xs);
  color: var(--ink-soft);
  background: var(--chip);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.connector small::before {
  content: "";
  width: 5px;
  height: 5px;
  flex: 0 0 5px;
  border-radius: 999px;
  background: currentColor;
}
```

5. `.cycleHealth` (linha ~1102): trocar `border-radius: 7px` por `border-radius: var(--radius-xs)`, `font-size: 11px` por `font-size: 10px`, e adicionar `font-family: var(--font-mono); letter-spacing: 0.08em;`.
6. `.brandTag` (linha ~240): trocar `border-radius: 999px;` por `border-radius: var(--radius-xs);`.

- [ ] **Step 3: Verificar**

Run: `pnpm dev` — Expected: badges retangulares mono caps; "VENCIDO"/"VENCE HOJE" vermelho, "3D" âmbar, "CONCLUÍDO" verde; status de conector com dot.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/globals.css
git commit -m "ui: badges de status mono caps retangulares (linguagem Handle)"
```

---

### Task 4: Shell — sidebar e appbar

**Files:**
- Modify: `frontend/app/globals.css` (seletores indicados)
- Modify: `frontend/app/page.tsx:837-840`

- [ ] **Step 1: CSS da sidebar:**

1. `.sidebar` (linha ~196): trocar `background: var(--panel-soft);` por `background: var(--sidebar);`.
2. Substituir o bloco `.navGroupLabel` (linha ~291) — label de seção vira mono caps:

```css
.navGroupLabel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 22px;
  padding: 0 6px;
  border: 0;
  background: transparent;
  color: var(--muted-2);
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  cursor: pointer;
}
```

3. Remover os dois blocos do item ativo com barra de acento (linhas ~360–370):

```css
/* REMOVER: */
.sideNav a.active,
.sideNav .navItem.active {
  box-shadow: inset 2px 0 0 var(--accent);
  font-weight: 600;
}

.sideNav a.active svg,
.sideNav .navItem.active svg {
  color: var(--accent);
}
```

E adicionar no lugar (ativo = chip + peso, sem cor):

```css
.sideNav a.active,
.sideNav .navItem.active {
  font-weight: 600;
}
```

4. `.sidebarCollapsed .sideNav a.active, ...` (linha ~372): trocar `box-shadow: inset 0 0 0 1px var(--accent-border);` por `box-shadow: none;`.

- [ ] **Step 2: Appbar — "Captura por OAB" vira ação primária. Em `frontend/app/page.tsx` (linha ~837), trocar:**

```tsx
            <button className="toolbarButton" onClick={openOab} disabled={offline}>
              <Search size={15} />
              Captura por OAB
            </button>
```

por:

```tsx
            <button className="toolbarButton primary" onClick={openOab} disabled={offline}>
              <Search size={15} />
              Captura por OAB
            </button>
```

- [ ] **Step 3: Verificar**

Run: `pnpm typecheck` — Expected: PASS.
Run: `pnpm dev` — Expected: sidebar quase branca com labels de seção em mono caps; item ativo cinza neutro sem barra teal; botão preto no topo direito.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/globals.css frontend/app/page.tsx
git commit -m "ui: sidebar neutra com labels mono e captura como ação primária"
```

---

### Task 5: Home — saudação display + statRow sem caixas

**Files:**
- Modify: `frontend/app/views/HomeDashboard.tsx`
- Modify: `frontend/app/page.tsx` (passar `greetingName`)
- Modify: `frontend/app/globals.css`

**Interfaces:**
- Consumes: `CommandStat` de `components/ui.tsx` (assinatura inalterada: `{ label, value, detail, tone? }`).
- Produces: prop nova `greetingName: string | null` em `HomeDashboard`; classes CSS `.homeHero`, `.heroGreeting`, `.heroDate`, `.heroPriority`, `.statRow`.

- [ ] **Step 1: Em `page.tsx`, derivar o primeiro nome da sessão.** Logo após a linha `const userEmail = session?.user?.email ?? null;` (~662), adicionar:

```tsx
  // Primeiro nome para a saudação da home (metadata do Supabase; sem fallback
  // para o e-mail — local-part não é nome apresentável).
  const userMeta = (session?.user?.user_metadata ?? {}) as Record<string, unknown>;
  const rawUserName =
    typeof userMeta.nome === "string"
      ? userMeta.nome
      : typeof userMeta.name === "string"
        ? userMeta.name
        : null;
  const greetingName = rawUserName?.trim().split(/\s+/)[0] ?? null;
```

E na chamada `<HomeDashboard` (linha ~967), adicionar a prop `greetingName={greetingName}`.

- [ ] **Step 2: Em `HomeDashboard.tsx`, adicionar a prop e substituir a seção `homeCommand`.** Adicionar `greetingName` na tipagem e destructuring:

```tsx
  greetingName: string | null;
```

Dentro do componente, antes do `return`, adicionar:

```tsx
  const hora = new Date().getHours();
  const saudacao = hora < 12 ? "Bom dia" : hora < 18 ? "Boa tarde" : "Boa noite";
  const dataLonga = new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric"
  }).format(new Date());
```

Substituir todo o bloco `<section className="homeCommand">…</section>` (do `<section className="homeCommand">` até o `</section>` que fecha `commandStats`) por:

```tsx
      <section className="homeHero">
        <div className="homeHeroText">
          <h1 className="heroGreeting">
            {saudacao}
            {greetingName ? `, ${greetingName}` : ""}
          </h1>
          <span className="heroDate">{dataLonga}</span>
          <p className="heroPriority">
            {metrics.highRisk > 0
              ? `${metrics.highRisk} prazo${metrics.highRisk > 1 ? "s" : ""} em alto risco. `
              : ""}
            {nextDeadline
              ? `${nextDeadline.prazo.descricao ?? "Prazo"} vence em ${formatDate(
                  nextDeadline.prazo.data_fatal
                )}.`
              : "A fila está sem vencimentos pendentes no momento."}
          </p>
        </div>
        <div className="quickActions">
          <LoadingButton
            className="toolbarButton primary"
            icon={<Search size={15} />}
            loading={busy === "capture"}
            onClick={onOpenOab}
            disabled={busy === "capture" || offline}
          >
            {busy === "capture" ? "Capturando..." : "Captura por OAB"}
          </LoadingButton>
          <button className="toolbarButton" onClick={onOpenAssistant} disabled={offline}>
            <MessageCircle size={15} />
            Assistente
          </button>
        </div>
      </section>

      <div className="statRow">
        <CommandStat label="Processos" value={metrics.monitored} detail="monitorados" />
        <CommandStat label="Intimações" value={metrics.captured} detail="capturadas" />
        <CommandStat label="Prazos" value={metrics.pending} detail="pendentes" />
        <CommandStat
          label="Prazos em dia"
          value={`${metrics.compliance}%`}
          detail={`${metrics.overdue} vencido(s)`}
          tone={metrics.overdue > 0 ? "risk" : metrics.highRisk > 0 ? "warn" : "ok"}
        />
      </div>
```

O texto "Prioridade operacional" e a contagem de alto risco continuam presentes via `heroPriority` — nada de informação é perdido.

- [ ] **Step 3: CSS.** Remover os blocos `.homeCommand` (linha ~977), `.primaryCommand` (~994), `.primaryCommand h2/strong/p` (~1013–1032) e `.commandStats` (~1041). Remover `.commandPanel` e `.commandStat` da lista do grupo `.commandPanel, .commandStat, .recordCard, ...` (linha ~983) — manter o grupo para as demais classes — e remover `.commandPanel` da lista de transições (linha ~5510); a classe `commandPanel` deixa de existir. Substituir os blocos `.commandStat`/`.commandStat span, small`/`.commandStat strong` por:

```css
/* KPI sem caixa (Handle): label mono caps + número gigante, hairlines entre células. */
.homeHero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: 22px 0 6px;
}

.homeHeroText {
  min-width: 0;
}

.heroGreeting {
  margin: 0;
  font-size: clamp(34px, 4.5vw, 52px);
  line-height: 1.02;
  font-weight: 500;
  letter-spacing: -0.03em;
}

.heroDate {
  display: block;
  margin-top: 10px;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.heroPriority {
  margin: 14px 0 0;
  max-width: 560px;
  color: var(--ink-soft);
  font-size: 13.5px;
  line-height: 1.5;
}

.statRow {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}

.commandStat {
  padding: 18px 20px 20px;
}

.commandStat + .commandStat {
  border-left: 1px solid var(--line);
}

.commandStat span {
  display: block;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.commandStat strong {
  display: block;
  margin-top: 10px;
  font-size: 38px;
  font-weight: 600;
  line-height: 1;
  letter-spacing: -0.02em;
}

.commandStat small {
  display: block;
  margin-top: 6px;
  color: var(--muted-2);
  font-size: 11px;
}
```

Manter os blocos `.commandStat.ok/.warn/.risk strong` como estão. Título dos painéis em mono caps — substituir `.panel header h2` implícito adicionando após o bloco `.panel header span`:

```css
.panel header h2 {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
```

- [ ] **Step 4: Responsivo.** Nas media queries, remover `.homeCommand` das listas (linhas ~2841 e ~2854) e adicionar no `@media (max-width: 1080px)`:

```css
  .homeHero {
    align-items: stretch;
    flex-direction: column;
  }

  .statRow {
    grid-template-columns: 1fr 1fr;
  }

  .commandStat:nth-child(odd) {
    border-left: 0;
  }

  .commandStat:nth-child(n + 3) {
    border-top: 1px solid var(--line);
  }
```

E no `@media (max-width: 680px)`, remover `.commandStats` da lista de `grid-template-columns: 1fr` (classe não existe mais).

- [ ] **Step 5: Verificar**

Run: `pnpm typecheck` — Expected: PASS.
Run: `pnpm dev` → Dashboard — Expected: "Boa tarde, {nome}" (ou só "Boa tarde" sem metadata) em display, data em mono caps, linha de 4 KPIs com hairlines e números grandes; sem caixas.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/views/HomeDashboard.tsx frontend/app/page.tsx frontend/app/globals.css
git commit -m "ui: home com saudação display e statRow sem caixas"
```

---

### Task 6: Título display nas views de registro

**Files:**
- Modify: `frontend/app/page.tsx:1044-1048`
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Em `page.tsx`, substituir o `viewTitleBlock`:**

```tsx
            <div className="viewTitleBlock">
              <span className="sectionKicker">{VIEW_LABEL[view]}</span>
              <strong>{viewCount.toLocaleString("pt-BR")} registros</strong>
            </div>
```

por:

```tsx
            <div className="viewTitleBlock">
              <h1 className="viewTitle">{VIEW_LABEL[view]}</h1>
              <span className="viewMeta">{viewCount.toLocaleString("pt-BR")} registros</span>
            </div>
```

- [ ] **Step 2: CSS.** Substituir os blocos `.viewbar` e `.viewTitleBlock strong/span` (linhas ~1420–1436) por:

```css
.viewbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 14px;
  margin: 12px 0 20px;
}

.viewTitle {
  margin: 0;
  font-size: clamp(28px, 3.2vw, 40px);
  line-height: 1.05;
  font-weight: 500;
  letter-spacing: -0.03em;
}

.viewMeta {
  display: block;
  margin-top: 8px;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 500;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-variant-numeric: tabular-nums;
}
```

(O `.viewTitleBlock strong` era referenciado na regra de `tabular-nums` da linha ~178 — trocar `.viewTitleBlock strong` por `.viewMeta` naquela lista.)

- [ ] **Step 3: Verificar + commit**

Run: `pnpm typecheck` && visual em Processos/Intimações/Prazos — título grande + contagem mono caps.

```bash
git add frontend/app/page.tsx frontend/app/globals.css
git commit -m "ui: títulos display nas views de registro"
```

---

### Task 7: Padrão dataTable + Fila do dia como tabela

**Files:**
- Modify: `frontend/app/globals.css` (novo padrão + remoção dos estilos de card da fila)
- Modify: `frontend/app/views/FilaDoDiaView.tsx`

**Interfaces:**
- Produces: classes genéricas `.dataTable`, `.dataHead`, `.dataRow` (+ `.dataRow.clickable`) e o modificador por view que define as colunas (ex.: `.filaTable`). **Tasks 8–12 dependem exatamente destes nomes.**
  - `.dataTable` = container com hairline + raio 8px.
  - `.dataHead` = linha de header mono caps (grid; colunas definidas pelo modificador).
  - `.dataRow` = linha de dados (mesmo grid do head).

- [ ] **Step 1: Adicionar o padrão genérico ao CSS** (logo antes do comentário `/* ---- Etapa 4 — Fila do dia... */`, linha ~4016):

```css
/* ===== Padrão Handle: tabela hairline ===== */
.dataTable {
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel);
}

.dataHead,
.dataRow {
  display: grid;
  align-items: center;
  gap: 14px;
  padding: 0 16px;
}

.dataHead {
  min-height: 34px;
  border-bottom: 1px solid var(--line);
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.dataRow {
  min-height: 60px;
  padding-top: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line);
  background: var(--panel);
}

.dataRow:last-child {
  border-bottom: 0;
}

.dataRow.clickable:hover {
  background: var(--panel-soft);
}

/* Célula título: linha principal + linha secundária. */
.dataRowMain {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.dataRowMain strong {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dataRowMain span {
  color: var(--muted);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dataRowEnd {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

/* Legenda de superfície (substitui os cards de introdução). */
.surfaceCaption {
  margin: 0;
  color: var(--muted);
  font-size: 12.5px;
}
```

- [ ] **Step 2: Colunas da fila + data flat.** Substituir os blocos `.filaIntro` (e filhos), `.filaList`, `.filaItem` (e variantes `.risk/.warn/.done`), `.filaDate` (e variantes), `.filaMain` (e filhos), `.filaMeta`, `.filaAction` (linhas ~4024–4170) por:

```css
.filaTable .dataHead,
.filaTable .dataRow {
  grid-template-columns: 84px minmax(0, 1fr) 170px minmax(170px, auto);
}

/* Data fatal sem caixa: dd/mm mono + ano, cor pelo risco. */
.filaDate {
  display: grid;
  gap: 2px;
}

.filaDate strong {
  font-family: var(--font-mono);
  font-size: 13.5px;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.01em;
}

.filaDate span {
  color: var(--muted-2);
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-variant-numeric: tabular-nums;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.filaDate.risk strong {
  color: var(--risk);
}

.filaDate.warn strong {
  color: var(--warn);
}

.filaDate.done strong {
  color: var(--ok);
}

.filaMeta {
  display: flex;
  align-items: center;
  justify-content: center;
}
```

Na media query `@media (max-width: 880px)` (linha ~4241), substituir as regras `.filaItem`/`.filaMain`/`.filaMeta`/`.filaAction` por:

```css
  .filaTable .dataHead {
    display: none;
  }

  .filaTable .dataRow {
    grid-template-columns: 84px minmax(0, 1fr);
  }

  .filaMeta {
    grid-column: 2;
    justify-content: flex-start;
  }

  .filaTable .dataRowEnd {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }
```

Remover também `.filaItem` das listas de transição/animação nas linhas ~5510–5576 (`.filaItem` não existe mais; trocar por `.dataRow` na lista de `itemIn` e de transições).

- [ ] **Step 3: JSX.** Em `FilaDoDiaView.tsx`, substituir o bloco `filaIntro` (linhas 147–153) por:

```tsx
      <p className="surfaceCaption">
        Worklist única priorizada por risco e proximidade do vencimento.
      </p>
```

E substituir o bloco `<div className="filaList">…</div>` (linhas 155–193) por:

```tsx
      <div className="dataTable filaTable">
        <div className="dataHead" aria-hidden="true">
          <span>Data fatal</span>
          <span>Peça / processo</span>
          <span>Status</span>
          <span className="dataRowEnd">Ação</span>
        </div>
        {visible.map((item) => {
          const peca =
            item.peticao?.tipo ?? item.prazo?.descricao ?? item.intimacao.tipo_comunicacao ?? "Ato a definir";
          const tone = tomDeRisco(item);
          const dataFatal = item.prazo ? formatDate(item.prazo.data_fatal) : null;
          return (
            <article className="dataRow" key={item.intimacao.id}>
              <div
                className={tone ? `filaDate ${tone}` : "filaDate"}
                title={dataFatal ? `Data fatal ${dataFatal}` : "Prazo ainda não calculado"}
              >
                {dataFatal ? (
                  <>
                    <strong>{dataFatal.slice(0, 5)}</strong>
                    <span>{dataFatal.slice(-4)}</span>
                  </>
                ) : (
                  <>
                    <strong>—</strong>
                    <span>s/ prazo</span>
                  </>
                )}
              </div>
              <div className="dataRowMain">
                <strong>{peca}</strong>
                <span className="mono">
                  {item.intimacao.numero_processo ?? item.processo?.numero ?? "Processo não identificado"}
                </span>
              </div>
              <div className="filaMeta">{badgeDePrazo(item)}</div>
              <div className="dataRowEnd">{acaoPrincipal(item)}</div>
            </article>
          );
        })}
        {!ordered.length ? (
          <Empty label="Fila vazia — rode uma captura por OAB ou aguarde novas intimações" />
        ) : null}
      </div>
```

Nenhuma mudança em `acaoPrincipal`, ordenação ou paginação.

- [ ] **Step 4: Verificar**

Run: `pnpm typecheck` — PASS. `pnpm dev` → Dashboard (worklist) — Expected: tabela com header mono caps DATA FATAL / PEÇA / STATUS / AÇÃO, linhas hairline, botões por linha funcionando (gerar minuta, aprovar).

- [ ] **Step 5: Commit**

```bash
git add frontend/app/globals.css frontend/app/views/FilaDoDiaView.tsx
git commit -m "ui: padrão dataTable hairline e fila do dia como tabela"
```

---

### Task 8: Intimações como tabela

**Files:**
- Modify: `frontend/app/views/IntimacoesView.tsx` (arquivo inteiro)
- Modify: `frontend/app/globals.css` (colunas + limpeza)

**Interfaces:**
- Consumes: `.dataTable/.dataHead/.dataRow/.dataRowMain/.dataRowEnd` da Task 7; badges da Task 3.

- [ ] **Step 1: Substituir o conteúdo de `IntimacoesView.tsx` por:**

```tsx
"use client";

import { Loader2, Sparkles } from "lucide-react";
import { formatDate, sistemaBadge, statusLabel } from "@/lib/format";
import { previewText } from "@/lib/sanitize";
import type { IntimacaoRow } from "@/lib/views";
import { DeadlineBadge, Empty } from "../components/ui";

export default function IntimacoesView({
  rows,
  busy,
  offline,
  onOpen,
  onGenerateDraft
}: {
  rows: IntimacaoRow[];
  busy: string | null;
  offline: boolean;
  onOpen: (intimacaoId: number) => void;
  onGenerateDraft: (intimacaoId: number) => void;
}) {
  return (
    <section className="dataTable inboxTable">
      <div className="dataHead" aria-hidden="true">
        <span>Intimação</span>
        <span>Processo</span>
        <span>Sistema</span>
        <span>Prazo</span>
        <span>Minuta</span>
        <span className="dataRowEnd">Ação</span>
      </div>
      {rows.map(({ intimacao, processo, prazo, peticao }) => (
        <article
          className="dataRow clickable"
          key={intimacao.id}
          onClick={() => onOpen(intimacao.id)}
        >
          <div className="dataRowMain">
            <strong>{intimacao.tipo_comunicacao ?? "Comunicação judicial"}</strong>
            <span>{previewText(intimacao.teor ?? "") || "Teor não informado"}</span>
          </div>
          <div className="dataRowMain">
            <strong className="mono">
              {intimacao.numero_processo ?? processo?.numero ?? "Não identificado"}
            </strong>
            <span>
              {intimacao.tribunal ?? processo?.tribunal ?? "-"} ·{" "}
              {formatDate(intimacao.data_publicacao ?? intimacao.data_disponibilizacao)}
            </span>
          </div>
          <span className={`pill ${sistemaBadge(processo?.sistema).className}`}>
            {sistemaBadge(processo?.sistema).label}
          </span>
          <DeadlineBadge prazo={prazo} />
          <span className={`queueStatus ${peticao?.status ?? "capturada"}`}>
            {peticao ? statusLabel(peticao.status) : "Sem minuta"}
          </span>
          <div className="dataRowEnd">
            <button
              className="toolbarButton compact"
              disabled={busy === `draft-${intimacao.id}` || offline}
              onClick={(e) => {
                e.stopPropagation();
                onGenerateDraft(intimacao.id);
              }}
            >
              {busy === `draft-${intimacao.id}` ? (
                <Loader2 className="spin" size={15} />
              ) : (
                <Sparkles size={15} />
              )}
              Minutar
            </button>
          </div>
        </article>
      ))}
      {!rows.length ? <Empty label="Nenhuma intimação encontrada" /> : null}
    </section>
  );
}
```

Toda informação do card antigo está na tabela (tipo, teor, processo, tribunal, data, sistema, prazo, status de minuta, ação). O ícone decorativo `inboxMarker` sai.

- [ ] **Step 2: CSS.** Adicionar junto ao `.filaTable` (Task 7):

```css
.inboxTable .dataHead,
.inboxTable .dataRow {
  grid-template-columns: minmax(0, 1.5fr) minmax(0, 1.1fr) 92px 96px 130px auto;
}

.dataRow > .pill,
.dataRow > .queueStatus,
.dataRow > .dayBadge {
  justify-self: start;
}

@media (max-width: 1080px) {
  .inboxTable .dataHead {
    display: none;
  }

  .inboxTable .dataRow {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .inboxTable .dataRow > .pill,
  .inboxTable .dataRow > .queueStatus,
  .inboxTable .dataRow > .dayBadge {
    grid-column: 1;
  }

  .inboxTable .dataRowEnd {
    grid-column: 2;
    grid-row: 1;
  }
}
```

Remover os blocos agora órfãos: `.inboxList`, `.inboxItem`, `.inboxMarker`, `.inboxContent`, `.inboxMeta`, `.inboxTeor` (e as referências a `.inboxItem` em `.clickable:hover`, listas de grupo das linhas ~985, ~1585–1612 e media queries ~2979–3000 — retirar apenas o nome da classe das listas, mantendo o resto).

- [ ] **Step 3: Verificar + commit**

Run: `pnpm typecheck` — PASS. Visual: linhas clicáveis abrem o drawer; Minutar funciona sem abrir o drawer (stopPropagation preservado).

```bash
git add frontend/app/views/IntimacoesView.tsx frontend/app/globals.css
git commit -m "ui: intimações como tabela hairline"
```

---

### Task 9: Processos como tabela

**Files:**
- Modify: `frontend/app/views/ProcessosView.tsx` (arquivo inteiro)
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Substituir o conteúdo de `ProcessosView.tsx` por:**

```tsx
"use client";

import { formatDate, sistemaBadge } from "@/lib/format";
import type { ProcessoRow } from "@/lib/views";
import { DeadlineBadge, Empty } from "../components/ui";

export default function ProcessosView({
  rows,
  onOpen
}: {
  rows: ProcessoRow[];
  onOpen: (id: number) => void;
}) {
  return (
    <section className="dataTable processTable">
      <div className="dataHead" aria-hidden="true">
        <span>Processo</span>
        <span>Órgão julgador</span>
        <span>Sistema</span>
        <span>Intimações</span>
        <span>Minutas</span>
        <span>Próximo prazo</span>
      </div>
      {rows.map(({ processo, intimacoes, peticoes, proximoPrazo }) => (
        <article
          className="dataRow clickable"
          key={processo.id}
          onClick={() => onOpen(processo.id)}
        >
          <div className="dataRowMain">
            <strong className="mono">{processo.numero}</strong>
            <span>{processo.classe ?? "Classe não informada"}</span>
          </div>
          <div className="dataRowMain">
            <strong>{processo.tribunal ?? "-"}</strong>
            <span>{processo.orgao_julgador ?? "Órgão não informado"}</span>
          </div>
          <span className={`pill ${sistemaBadge(processo.sistema).className}`}>
            {sistemaBadge(processo.sistema).label}
          </span>
          <span className="cellCount">{intimacoes.length}</span>
          <span className="cellCount">{peticoes.length}</span>
          <div className="dataRowEnd">
            <span className="cellDate">
              {proximoPrazo ? formatDate(proximoPrazo.data_fatal) : "—"}
            </span>
            <DeadlineBadge prazo={proximoPrazo} />
          </div>
        </article>
      ))}
      {!rows.length ? <Empty label="Nenhum processo encontrado" /> : null}
    </section>
  );
}
```

A barra `recordProgress` (largura sintética decorativa) sai; contagens e datas continuam.

- [ ] **Step 2: CSS.** Adicionar:

```css
.processTable .dataHead,
.processTable .dataRow {
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr) 92px 84px 72px minmax(180px, auto);
}

.cellCount {
  font-family: var(--font-mono);
  font-size: 12.5px;
  font-variant-numeric: tabular-nums;
}

.cellDate {
  color: var(--ink-soft);
  font-family: var(--font-mono);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

@media (max-width: 1080px) {
  .processTable .dataHead {
    display: none;
  }

  .processTable .dataRow {
    grid-template-columns: minmax(0, 1fr) auto;
  }
}
```

Remover os blocos órfãos de `.recordCard`/`.recordMeta`/`.recordFooter`/`.recordProgress`/`.moduleGrid` e retirar `.recordCard` das listas compartilhadas (linhas ~985, ~1582–1623, hover ~3592, ~5120, ~5510, ~5529).

- [ ] **Step 3: Verificar + commit**

```bash
git add frontend/app/views/ProcessosView.tsx frontend/app/globals.css
git commit -m "ui: processos como tabela hairline"
```

---

### Task 10: Prazos como tabela

**Files:**
- Modify: `frontend/app/views/PrazosView.tsx` (arquivo inteiro)
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Substituir o conteúdo de `PrazosView.tsx` por:**

```tsx
"use client";

import { CalendarDays, CheckCircle2, ChevronRight, Loader2 } from "lucide-react";
import type { Prazo } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { PrazoRow } from "@/lib/views";
import type { DetailSelection } from "../DetailDrawer";
import { DeadlineBadge, Empty } from "../components/ui";

export default function PrazosView({
  rows,
  busy,
  offline,
  onOpen,
  onDonePrazo,
  onEditPrazo
}: {
  rows: PrazoRow[];
  busy: string | null;
  offline: boolean;
  onOpen: (sel: DetailSelection) => void;
  onDonePrazo: (prazo: Prazo) => void;
  onEditPrazo: (prazo: Prazo) => void;
}) {
  return (
    <section className="dataTable deadlineTable">
      <div className="dataHead" aria-hidden="true">
        <span>Data fatal</span>
        <span>Prazo / processo</span>
        <span>Ato vinculado</span>
        <span>Status</span>
        <span className="dataRowEnd">Ações</span>
      </div>
      {rows.map(({ prazo, processo, intimacao, peticao, dias }) => {
        const target: DetailSelection | null = processo
          ? { kind: "processo", id: processo.id }
          : intimacao
            ? { kind: "intimacao", id: intimacao.id }
            : null;
        const tone = prazo.cumprido ? "done" : dias <= 1 ? "risk" : dias <= 3 ? "warn" : "";
        return (
          <article className="dataRow" key={prazo.id}>
            <div className={tone ? `filaDate ${tone}` : "filaDate"}>
              <strong>{formatDate(prazo.data_fatal).slice(0, 5)}</strong>
              <span>{dias < 0 ? "vencido" : `${dias}d`}</span>
            </div>
            <div className="dataRowMain">
              <strong>{prazo.descricao ?? "Prazo"}</strong>
              <span className="mono">
                {processo?.numero ?? `Processo #${prazo.processo_id ?? "-"}`}
              </span>
            </div>
            <span className="cellText">
              {intimacao?.tipo_comunicacao ?? peticao?.tipo ?? "Não informado"}
            </span>
            <DeadlineBadge prazo={prazo} />
            <div className="dataRowEnd">
              {target ? (
                <button className="toolbarButton compact" onClick={() => onOpen(target)}>
                  <ChevronRight size={15} />
                  Detalhes
                </button>
              ) : null}
              <button
                className="toolbarButton compact"
                disabled={prazo.cumprido || busy === `done-${prazo.id}` || offline}
                onClick={() => onDonePrazo(prazo)}
              >
                {busy === `done-${prazo.id}` ? (
                  <Loader2 className="spin" size={15} />
                ) : (
                  <CheckCircle2 size={15} />
                )}
                Cumprir
              </button>
              <button
                className="toolbarButton compact"
                disabled={busy === `edit-${prazo.id}` || offline}
                onClick={() => void onEditPrazo(prazo)}
              >
                {busy === `edit-${prazo.id}` ? (
                  <Loader2 className="spin" size={15} />
                ) : (
                  <CalendarDays size={15} />
                )}
                Revisar
              </button>
            </div>
          </article>
        );
      })}
      {!rows.length ? <Empty label="Nenhum prazo encontrado" /> : null}
    </section>
  );
}
```

- [ ] **Step 2: CSS.** Adicionar:

```css
.deadlineTable .dataHead,
.deadlineTable .dataRow {
  grid-template-columns: 84px minmax(0, 1.2fr) minmax(0, 0.8fr) 110px minmax(280px, auto);
}

.cellText {
  color: var(--ink-soft);
  font-size: 12.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 1080px) {
  .deadlineTable .dataHead {
    display: none;
  }

  .deadlineTable .dataRow {
    grid-template-columns: 84px minmax(0, 1fr);
  }

  .deadlineTable .dataRowEnd {
    grid-column: 1 / -1;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
```

Remover os blocos órfãos `.deadlineBoard`, `.deadlineCard`, `.deadlineMain` (e filhos) e `.dateBlock`/`.dateBlock.large` **somente se** `dateBlock` não for usado em outro lugar — ele é usado em `HomeDashboard.tsx` (agenda de prazos). Manter `.dateBlock` e remover apenas `.deadlineBoard/.deadlineCard/.deadlineMain`; retirar `.deadlineCard` das listas compartilhadas (~985, ~1587, ~2983, ~2999).

- [ ] **Step 3: Verificar + commit**

Ações Cumprir/Revisar/Detalhes funcionam por linha.

```bash
git add frontend/app/views/PrazosView.tsx frontend/app/globals.css
git commit -m "ui: prazos como tabela hairline"
```

---

### Task 11: Minutas como tabela

**Files:**
- Modify: `frontend/app/views/PeticoesView.tsx` (arquivo inteiro)
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Substituir o conteúdo de `PeticoesView.tsx` por:**

```tsx
"use client";

import { FilePenLine } from "lucide-react";
import type { Peticao } from "@/lib/api";
import { formatDate, sistemaBadge, statusLabel } from "@/lib/format";
import type { PeticaoRow } from "@/lib/views";
import { Empty } from "../components/ui";

export default function PeticoesView({
  rows,
  onOpenEditor,
  onGoToGate
}: {
  rows: PeticaoRow[];
  onOpenEditor: (peticao: Peticao) => void;
  onGoToGate: () => void;
}) {
  return (
    <section className="redactionBoard">
      <p className="surfaceCaption">
        Revise e edite o conteúdo das minutas. A aprovação e o protocolo acontecem no{" "}
        <button className="linkButton" onClick={onGoToGate}>
          Gate OAB
        </button>
        .
      </p>

      <div className="dataTable redactionTable">
        <div className="dataHead" aria-hidden="true">
          <span>Minuta</span>
          <span>Processo</span>
          <span>Status</span>
          <span>Sistema</span>
          <span>Prazo</span>
          <span className="dataRowEnd">Ação</span>
        </div>
        {rows.map(({ peticao, processo, prazo }) => (
          <article
            className="dataRow clickable"
            key={peticao.id}
            onClick={() => onOpenEditor(peticao)}
          >
            <div className="dataRowMain">
              <strong>{peticao.tipo ?? "Petição"}</strong>
              <span>{peticao.conteudo ?? "Sem conteúdo"}</span>
            </div>
            <span className="cellDate mono">
              {processo?.numero ?? `Processo #${peticao.processo_id}`}
            </span>
            <span className={`pill ${peticao.status}`}>{statusLabel(peticao.status)}</span>
            <span className={`pill ${sistemaBadge(processo?.sistema).className}`}>
              {sistemaBadge(processo?.sistema).label}
            </span>
            <span className="cellDate">
              {prazo ? formatDate(prazo.data_fatal) : "—"}
            </span>
            <div className="dataRowEnd">
              <span className="redactionOpen">
                <FilePenLine size={14} />
                Abrir editor
              </span>
            </div>
          </article>
        ))}
        {!rows.length ? <Empty label="Nenhuma minuta encontrada" /> : null}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: CSS.** Adicionar:

```css
.redactionTable .dataHead,
.redactionTable .dataRow {
  grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr) 110px 92px 92px auto;
}

@media (max-width: 1080px) {
  .redactionTable .dataHead {
    display: none;
  }

  .redactionTable .dataRow {
    grid-template-columns: minmax(0, 1fr) auto;
  }
}
```

Remover os blocos órfãos `.redactionIntro`, `.redactionList`, `.redactionCard` (e filhos header/tags/preview/foot — manter `.redactionOpen` e `.linkButton`, ainda usados) e retirar `.redactionCard` das listas de hover (~3592, ~5531).

- [ ] **Step 3: Verificar + commit**

```bash
git add frontend/app/views/PeticoesView.tsx frontend/app/globals.css
git commit -m "ui: minutas como tabela hairline"
```

---

### Task 12: Auditoria como tabela + Protocolos flat

**Files:**
- Modify: `frontend/app/AuditPanel.tsx`
- Modify: `frontend/app/globals.css`

> **Divergência consciente do spec:** o spec lista Protocolos entre as views que
> viram tabela, mas cada job carrega conteúdo aninhado interativo (passos de
> handoff, formulário "registrar protocolo") que não cabe em uma linha de
> tabela. Protocolos segue a regra dos "cards informativos": cards flat com
> hairline. Se o usuário preferir tabela mesmo assim, tratar em follow-up.

- [ ] **Step 1: Em `AuditPanel.tsx`, substituir o `return` (linhas 61–83) por:**

```tsx
  return (
    <section className="panel">
      <header>
        <h2>
          <Table2 size={13} /> Auditoria
        </h2>
        <span>trilha imutável</span>
      </header>
      {error ? <div className="assistantError">{error}</div> : null}
      <div className="auditList">
        <div className="dataHead auditHead" aria-hidden="true">
          <span>Ação</span>
          <span>Ator / entidade</span>
        </div>
        {logs.map((log) => (
          <article className="dataRow auditRow" key={log.id}>
            <strong>{log.acao}</strong>
            <span>
              {auditActorLabel(log.ator, userNames)} · {log.entidade ?? "-"}
              {log.entidade_id != null ? ` #${log.entidade_id}` : ""}
            </span>
          </article>
        ))}
        {!logs.length && !error ? <div className="empty">Sem eventos registrados</div> : null}
      </div>
    </section>
  );
```

- [ ] **Step 2: CSS.** Adicionar (e remover o bloco `.auditLogRow` e filhos, linha ~2684):

```css
.auditHead,
.auditRow {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr);
}

.auditRow {
  min-height: 44px;
}

.auditRow strong {
  font-size: 12.5px;
}

.auditRow span {
  color: var(--muted);
  font-size: 12px;
}
```

- [ ] **Step 3: Protocolos flat (CSS only).**

1. `.protocolCard` (linha ~4658): trocar `border-radius: 12px;` por `border-radius: var(--radius-md);` e `background: var(--panel-soft);` por `background: var(--panel);`.
2. `.protocolMeta dt` (linha ~4731): adicionar `font-family: var(--font-mono); letter-spacing: 0.08em;` (substituindo o `letter-spacing: 0.05em`).
3. `.protocolHead strong` (linha ~4639): substituir o bloco por:

```css
.protocolHead strong {
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
```

- [ ] **Step 4: Verificar + commit**

```bash
git add frontend/app/AuditPanel.tsx frontend/app/globals.css
git commit -m "ui: auditoria como tabela e protocolos flat"
```

---

### Task 13: Varredura final de raios, sombras e cores literais

**Files:**
- Modify: `frontend/app/globals.css`

Flatten do que sobrou fora dos tokens. Cada item é seletor → edição exata:

- [ ] **Step 1: Modais e drawers**

1. `.modalCard` (~3024): `border-radius: 12px` → `border-radius: var(--radius-xl)`.
2. `.filterPanel` (~3492): `border-radius: 10px` → `var(--radius-md)`.
3. `.radarPanel` (~4300): `border-radius: 12px` → `var(--radius-md)`; `box-shadow: 0 24px 60px -24px rgba(0,0,0,0.18)` → `box-shadow: var(--shadow-lg)`.
4. `.searchSelectPopover` (~3153): borda `color-mix(... var(--accent))` → `1px solid var(--line-strong)`.

- [ ] **Step 2: classificationNotice — de literais coloridos para tokens flat.** Substituir os blocos `.classificationNotice`, `.classificationNotice.success`, `.classificationNoticeIcon`, `.classificationNotice.success .classificationNoticeIcon` e `.classificationNoticeConfidence` (linhas ~631–717) por:

```css
.classificationNotice {
  align-items: stretch;
  gap: 14px;
  padding: 14px 16px;
  border-color: color-mix(in srgb, var(--risk) 30%, var(--line));
  border-radius: var(--radius-md);
  background: var(--risk-bg);
  box-shadow: none;
}

.classificationNotice.success {
  border-color: color-mix(in srgb, var(--ok) 30%, var(--line));
  background: var(--ok-bg);
}

.classificationNoticeIcon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  border-radius: var(--radius-sm);
  border: 1px solid color-mix(in srgb, var(--risk) 24%, var(--line));
  background: var(--panel);
  color: var(--risk);
  box-shadow: none;
}

.classificationNotice.success .classificationNoticeIcon {
  border-color: color-mix(in srgb, var(--ok) 24%, var(--line));
  color: var(--ok);
}

.classificationNoticeConfidence {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: var(--radius-xs);
  border: 0;
  background: color-mix(in srgb, var(--panel) 72%, transparent);
  color: var(--ink-soft);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  white-space: nowrap;
}
```

Remover o bloco `.classificationNotice.success .classificationNoticeConfidence` (borda literal, agora sem borda).

- [ ] **Step 3: Assistente — raios e sombras.**

1. `.assistantHistoryPanel` (~2111): `border-radius: 18px` → `var(--radius-md)`; `box-shadow: 0 16px 38px rgba(15,23,42,0.05)` → `box-shadow: none`; borda → `1px solid var(--line)`.
2. `.assistantSessionHeader` (~2288): `border-radius: 18px` → `var(--radius-md)`; `box-shadow: ...` → `none`; background composto → `background: var(--panel);`.
3. `.chatSurface` (~2340): `border-radius: 24px` → `var(--radius-lg)`; `box-shadow: ...` → `none`; background composto → `background: var(--panel);`. Remover o bloco `.chatSurface::before` (moldura interna decorativa) e o `.chatSurface > * { position: relative; z-index: 1; }`.
4. `.assistantWorkspace` (~2098): remover o `background:` composto (radial + linear) — fica sem background (herda `--bg`).
5. `.promptSuggestions button` (~2418): `border-radius: 18px` → `var(--radius-md)`; `box-shadow: ...` → `none`; no `:hover` remover `transform` e `box-shadow` (manter troca de borda/fundo).
6. `.assistantThread` (~2160): `border-radius: 13px` → `var(--radius-sm)`. No `.assistantThread.active` (~2170): substituir por:

```css
.assistantThread.active {
  border-color: var(--line-strong);
  background: var(--chip);
  box-shadow: none;
}
```

7. `.chatBubble span` (~2488): `border-radius: 16px` → `var(--radius-md)`; `box-shadow: ...` → `none`.
8. `.assistantComposer` (~2563): `border-radius: 20px` → `var(--radius-lg)`; `box-shadow: ...` → `var(--shadow-md)`. `.assistantComposer .iconButton` (~2593): `border-radius: 15px` → `var(--radius-sm)`.
9. `.assistantIntroBadge` (~2389): `border-radius: 999px` → `var(--radius-xs)`; adicionar `font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em;` (substituindo `font-size: 12px`).
10. `.assistantSessionStats span` (~2330): `border-radius: 999px` → `var(--radius-xs)`.
11. `.assistantActionCard` (~2524): `border-radius: 16px` → `var(--radius-md)`; background composto → `background: var(--warn-bg);`.
12. `.assistantThreadEmpty` (~2247): `border-radius: 14px` → `var(--radius-md)`. `.assistantClearHistory` (~2264): `border-radius: 11px` → `var(--radius-sm)`.

- [ ] **Step 4: Diversos.**

1. `.sidebarToggle` (~254): remover `box-shadow: 0 8px 22px rgb(15 23 42 / 7%);`.
2. `.authShell` (~4952): manter o gradiente (com `--accent-bg` cinza vira um halo neutro sutil — ok).
3. `.recordCard header small` — já removido na Task 9 (conferir que nenhuma referência órfã sobrou: `grep -n "recordCard" frontend/app/globals.css` deve retornar vazio).
4. `.onboardingHero` (~854) e `.primaryCommand`: `.onboardingHero` mantém `border-left: 4px solid var(--accent)` — com accent preto vira barra preta; trocar por `border-left: 1px solid var(--line)` (flat, sem barra).
5. `.gateLane > header span` (~1757): `border-radius: 999px` → manter (bubble de contagem circular é ok, igual `tabCount`).
6. Overrides `[data-theme="dark"]` do topo (linhas 80–126): manter todos — continuam corretos com os novos tokens (conferir visualmente no escuro).

- [ ] **Step 5: Verificar + commit**

Run: `pnpm typecheck && pnpm lint` — PASS. Visual: assistente, modais, notices e login flat nos 2 temas.

```bash
git add frontend/app/globals.css
git commit -m "ui: varredura flat final (modais, assistente, notices, literais)"
```

---

### Task 14: Verificação completa

**Files:**
- Create: `backend/scripts/ui_smoke_redesign.py` (screenshots autenticados, 2 temas)

- [ ] **Step 1: Checks estáticos**

Run (em `/frontend`): `pnpm check` — Expected: lint + typecheck + vitest PASS.
Run: `pnpm build` — Expected: build de produção PASS.

- [ ] **Step 2: Grep de resíduos**

Run: `grep -n "0f766e\|99f6e4\|ecfdf5\|2dd4bf" frontend/app/globals.css` — Expected: vazio (teal extinto).
Run: `grep -rn "filaItem\|inboxItem\|recordCard\|deadlineCard\|redactionCard\|auditLogRow\|homeCommand\|commandStats\|commandPanel\|primaryCommand" frontend/app` — Expected: vazio (classes órfãs extintas).

- [ ] **Step 3: Smoke visual autenticado.** Criar `backend/scripts/ui_smoke_redesign.py`:

```python
"""Smoke visual do redesign Handle: telas principais nos 2 temas.

Uso: python scripts/ui_smoke_redesign.py [dir_saida]
Pressupõe frontend em :3000, backend em :8000 e credenciais em
CAUSOR_SMOKE_EMAIL / CAUSOR_SMOKE_PASSWORD (conta de piloto/demo).
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

out = Path(sys.argv[1] if len(sys.argv) > 1 else "shots/redesign")
out.mkdir(parents=True, exist_ok=True)

email = os.environ["CAUSOR_SMOKE_EMAIL"]
password = os.environ["CAUSOR_SMOKE_PASSWORD"]

VIEWS = ["Dashboard", "Intimações", "Processos", "Prazos", "Minutas", "Protocolos", "Conectores", "Auditoria"]

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:3000", wait_until="networkidle")
    if page.get_by_placeholder("voce@escritorio.com.br").count() or page.locator("input[type=email]").count():
        page.locator("input[type=email]").fill(email)
        page.locator("input[type=password]").fill(password)
        page.get_by_role("button", name="Entrar").click()
        page.wait_for_timeout(2500)

    for theme in ("light", "dark"):
        page.evaluate(
            "t => { if (t === 'dark') document.documentElement.dataset.theme = 'dark';"
            " else delete document.documentElement.dataset.theme; }",
            theme,
        )
        for view in VIEWS:
            page.get_by_role("button", name=view, exact=True).first.click()
            page.wait_for_timeout(900)
            slug = view.lower().replace("ç", "c").replace("õ", "o").replace("á", "a")
            page.screenshot(path=str(out / f"{theme}-{slug}.png"))

    browser.close()

print(f"screenshots em {out.resolve()}")
```

Run (backend rodando com seed + frontend `pnpm dev`):
`cd backend && CAUSOR_SMOKE_EMAIL=... CAUSOR_SMOKE_PASSWORD=... ./.venv/Scripts/python.exe scripts/ui_smoke_redesign.py`
Expected: 16 PNGs em `backend/shots/redesign/`.
**Se as credenciais de smoke não estiverem disponíveis, parar e pedir ao usuário que rode o app e valide visualmente — não inventar credenciais.**

- [ ] **Step 4: Comparação com a referência.** Abrir os screenshots ao lado de `handle dashboard.png` e `handle ui.png` e conferir a checklist:

- canvas branco puro, sem cinza de fundo (claro) / preto quase puro (escuro);
- KPIs sem caixa com hairlines verticais e números grandes;
- tabelas com header mono caps e linhas hairline;
- botão primário preto (claro) / branco (escuro), retangular;
- badges mono caps com cor apenas semântica;
- saudação display na home com data em mono caps;
- nenhum teal visível em nenhuma tela.

- [ ] **Step 5: Fluxo funcional intacto.** No app: gerar minuta → revisar → aprovar → protocolar (simulado) a partir da fila; abrir drawer de detalhe; alternar tema; colapsar sidebar. Expected: tudo funciona como antes.

- [ ] **Step 6: Commit final**

```bash
git add backend/scripts/ui_smoke_redesign.py backend/shots/redesign
git commit -m "ui: smoke visual do redesign Handle (screenshots 2 temas)"
```
