# Reforma visual "Causor × Handle" — design aprovado

Data: 2026-07-05
Status: aprovado pelo usuário (brainstorming concluído)
Referências visuais: `handle dashboard.png` e `handle ui.png` na raiz do repositório.

## Objetivo

Aproximar a UI do Causor da linguagem visual do Handle.ai (referência nos dois
PNGs): branco dominante, divisores hairline no lugar de cards com sombra,
tipografia como protagonista (títulos display gigantes + micro-labels
monoespaçados em maiúsculas) e paleta quase monocromática com cor apenas
semântica. Nenhum comportamento, rota, dado ou endpoint muda — a reforma é
exclusivamente de apresentação.

Decisões fechadas com o usuário (não re-litigar):

1. **Cor**: monocromático como o Handle. Preto/branco dominante; teal sai da
   UI. Vermelho reservado a risco/vencido, âmbar discreto para "vence em ≤3
   dias", verde para cumprido/ativo.
2. **Escopo**: app inteiro de uma vez (tokens globais + ajustes estruturais em
   todas as telas).
3. **Dark mode**: os dois temas são atualizados na mesma lógica; claro é a
   referência, escuro é a retradução.
4. **Tipografia**: manter Inter + JetBrains Mono; refinar tamanhos, pesos e
   tracking (sem fonte nova).
5. **Home**: adota saudação gigante ("Bom dia/Boa tarde/Boa noite, {primeiro
   nome}") + data por extenso em mono caps.
6. **Abordagem técnica**: tokens primeiro (efeito global imediato), depois
   cirurgia pontual por tela onde CSS não alcança (KPIs sem caixa, listas →
   tabelas, saudação).

## 1. Tokens globais (`frontend/app/globals.css`)

### Tema claro (`:root`)

| Token | Hoje | Novo | Racional |
| --- | --- | --- | --- |
| `--bg` | `#f5f6f8` | `#ffffff` | canvas branco puro como o Handle |
| `--panel` | `#ffffff` | `#ffffff` | mantém |
| `--panel-soft` | `#f8fafc` | `#fafafa` | cinza neutro (sem matiz slate) |
| `--sidebar` | `#f3f4f6` | `#fcfcfc` | sidebar quase branca + hairline à direita |
| `--ink` | `#111827` | `#111111` | preto neutro |
| `--ink-soft` | `#374151` | `#404040` | neutro |
| `--muted` | `#6b7280` | `#737373` | neutro (contraste AA em branco: 4.6:1) |
| `--muted-2` | `#9ca3af` | `#a3a3a3` | neutro |
| `--line` | `#e5e7eb` | `#ececec` | hairline |
| `--line-strong` | `#cbd5e1` | `#d4d4d4` | neutro |
| `--chip` | `#eef2f7` | `#f5f5f5` | neutro |
| `--accent` | `#0f766e` (teal) | `#111111` | accent = preto; teal sai |
| `--accent-bg` | `#ecfdf5` | `#f5f5f5` | fundo de item ativo neutro |
| `--accent-border` | `#99f6e4` | `#e0e0e0` | neutro |
| `--risk` | `#fb2c36` | mantém | vermelho semântico (Handle usa igual) |
| `--warn` | `#b45309` | mantém, uso mais discreto | tier "vence em ≤3d" |
| `--ok`/`--success` | `#166534` | mantém | cumprido/ativo ("● ATIVO") |
| `--shadow-sm/md/lg` | sombras slate | `none`/quase zero | sombra só em modal, dropdown, toast |
| `--radius-sm` | 8px | 6px | botões e inputs |
| `--radius-md/lg/xl` | 10/12/16px | 8/8/10px | cards e tabelas com cantos mais retos |
| `--radius-pill` | 999px | continua existindo | usar apenas em elementos realmente redondos (avatar, dot); botões deixam de usá-lo |

Raios de referência por elemento: botões/inputs 6px (`--radius-sm`),
cards/tabelas 8px (`--radius-md`), badges 4px (`--radius-xs`, inalterado).

### Tema escuro (`[data-theme="dark"]`)

Mesma lógica retraduzida: `--bg #0a0a0a`, `--panel #111113`,
`--panel-soft #17171a`, `--sidebar #0d0d0f`, `--line #222226`,
`--ink #f5f5f5`, `--accent #f5f5f5` (botão primário branco com texto preto),
semânticas dessaturadas (`--risk #f87171`, `--ok #4ade80`, `--warn #fbbf24`
sobre fundos tintados escuros). Os overrides `[data-theme="dark"]` existentes
que compensavam cores literais são revisados: os que ficarem redundantes com os
novos tokens são removidos.

## 2. Tipografia

- Título de página (display): ~48px (clamp para telas menores), peso 450–500,
  tracking -0.02em. Vale para títulos de view e para a saudação da home.
- Kicker/micro-label: JetBrains Mono, maiúsculas, 10–11px, letter-spacing
  0.08em, cor `--muted`. É a voz oficial de: labels de KPI, headers de tabela,
  badges de status, datas técnicas, kickers de seção.
- Corpo: 14px; texto secundário 13px.
- Números grandes de KPI: ~36px, peso 550, `tabular-nums`.

## 3. Shell — sidebar e topbar

- **Sidebar**: fundo `--sidebar` (quase branco) + hairline à direita; labels de
  seção (OPERAÇÃO DIÁRIA, AUTOMAÇÕES, REGISTRO, GOVERNANÇA) em mono caps 10px
  `--muted-2`; itens 13px com ícone 16px; item ativo = fundo `--chip` + texto
  `--ink` (sem cor de marca). Rodapé mantém Ajuda/Configurações/conta.
- **Topbar**: branco com hairline inferior; breadcrumb à esquerda (mantém);
  à direita, "Captura por OAB" vira **botão primário preto retangular** (estilo
  "+ New Request" do Handle) e o sino de notificações fica minimalista
  (ícone ghost + badge vermelho pequeno).

## 4. KPIs sem caixa — padrão `statRow`

Novo padrão de apresentação (CSS + pequeno ajuste de JSX onde necessário):
linha horizontal de células separadas por hairlines verticais; cada célula tem
label mono caps em cima e número gigante embaixo. Sem borda externa, sem fundo,
sem sombra.

- **Home**: `CommandStats` (Processos / Intimações / Prazos / Prazos em dia)
  vira `statRow` logo abaixo da saudação.
- **Demais telas**: a caixa cinza "PRAZOS EM DIA 83%" do header some; o dado
  vira stat compacto sem borda alinhado à direita do header (label mono caps +
  número grande).

## 5. Listas → tabelas hairline

Views de lista (Fila do dia, Intimações, Processos, Prazos, Minutas/Petições,
Protocolos, Auditoria) trocam cards empilhados por **tabela estilo Handle**:

- Container único com borda hairline e raio 8px.
- Header de colunas em mono caps 10px `--muted` (ex. na Fila do dia:
  PEÇA / PROCESSO / STATUS / PRAZO / AÇÃO).
- Linhas altas (~64px) separadas por hairline; hover `--panel-soft`.
- A ação principal da linha continua como botão (retangular, pequeno).
- Nenhuma ação, ordenação ou paginação muda de comportamento.
- As colunas exatas de cada view (a Fila do dia serve de exemplo acima) são
  enumeradas no plano de implementação, view a view, a partir dos campos que
  cada card exibe hoje — sem adicionar nem remover informação.

Onde a view é de cards informativos (Conectores, Central de Comando), os cards
permanecem cards, mas flat: hairline, raio 8px, sem sombra.

## 6. Botões, inputs e badges

- **Primário**: retangular 6px, fundo `--solid` (preto; branco no escuro),
  texto invertido, 13px peso 500.
- **Secundário**: fundo `--panel`, borda hairline, texto `--ink`.
- **Ghost**: só texto/ícone, hover `--chip`.
- **Inputs/selects/busca**: borda hairline, raio 6px, fundo `--panel`; busca
  com ícone à esquerda como a barra de filtros do Handle.
- **Tabs** (onde existem): texto 13px, ativo com underline 2px `--ink`.
- **Badges de status** (`dayBadge`, `pill`, `jobStatus` etc.): mono maiúsculo
  10px letter-spacing 0.08em, raio 4px, texto na cor semântica + fundo tintado
  sutil. Ex.: "VENCIDO HÁ 2D" (vermelho), "VENCE EM 3 DIAS" (âmbar),
  "CUMPRIDO" (verde), "SEM PRAZO" (cinza).
- **Status de conector**: dot + mono caps, ex. "● ATIVO" verde, "● PILOTO"
  âmbar, "● PLANEJADO" cinza — como o "● LIVE" do Handle.

## 7. Central de Comando (home)

- Abre com saudação display: "Bom dia/Boa tarde/Boa noite, {primeiro nome}"
  (deriva do horário local; nome do usuário autenticado, fallback "Bem-vindo").
- Abaixo, data por extenso em mono caps (ex. "SÁBADO, 5 DE JULHO DE 2026").
- Em seguida a `statRow` (seção 4) e o restante da home flat: ciclo do agente
  mantém a estrutura numerada (01, 02…) sem caixas com sombra; painéis
  ("Agenda de prazos", "Saúde operacional", "Áreas de trabalho") viram seções
  com hairline e título em mono caps.

## 8. Fora de escopo / invariantes

- Nenhuma mudança de rotas, dados, chamadas de API, textos funcionais, lógica
  de negócio ou acessibilidade estrutural (roles/aria).
- Login e modais herdam tokens e botões novos; sem redesenho estrutural além
  disso.
- Contraste AA verificado nos dois temas para texto de corpo e micro-labels.
- A landing page (`causor-landing`, repositório separado) não faz parte desta
  reforma.

## 9. Verificação

1. `tsc` (typecheck) e build do Next.js passam.
2. Passada visual: dev server + screenshots Playwright das telas principais
   (home, Fila do dia, Intimações, Prazos, Protocolos, Conectores, Auditoria,
   login, um modal) nos dois temas; comparação lado a lado com os PNGs de
   referência.
3. Sem regressão funcional: fluxo gerar minuta → aprovar → protocolar continua
   operável na UI.
