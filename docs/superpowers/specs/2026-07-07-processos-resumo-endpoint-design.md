# Página de Processos escalável — endpoint enriquecido — design aprovado

Data: 2026-07-07
Status: aprovado pelo usuário (brainstorming concluído)

## Contexto e problema

A página de Processos monta suas linhas cruzando **quatro tabelas capadas** no
navegador: `/processos`, `/prazos`, `/intimacoes`, `/peticoes` (todas com
`limit` default 100, teto 500). O `processoRows` faz o join processo → próximo
prazo → intimações → petições client-side, e a contagem do cabeçalho é o
`.length` desse resultado.

Consequência já observada: o dashboard mostrava 200 processos monitorados
(contagem server-side em `/dashboard/operational`) e a página mostrava 195 —
porque a união das listas paginadas (`/processos` capado + processos vindos do
`/review/queue`) cobria só 195 dos 200. Cinco processos ficavam **invisíveis na
tabela**, não só num número errado. Um stopgap subiu `/processos` para
`limit=500` (commit anterior nesta branch), mas isso só adia a parede: baixar e
cruzar tabelas inteiras no cliente não escala.

Alvo de escala decidido com o usuário: **até ~3 mil processos por conta
(escritório)**. Nesse teto não é preciso paginação server-side de verdade
(seria YAGNI); é preciso parar de derivar a lista de tabelas capadas e trazer
contagem + linhas já cruzadas do servidor.

## Decisões fechadas com o usuário (não re-litigar)

1. **Abordagem B — endpoint enriquecido.** Um endpoint devolve cada processo já
   cruzado no servidor (próximo prazo, contagens, campos de busca) + o `total`
   real. A página consome uma lista auto-suficiente; some o join de 4 tabelas no
   cliente.
2. **Escopo: só a página de Processos.** Intimações/Prazos/Petições têm o mesmo
   problema latente, mas ficam fora deste spec.
3. **Não mexer no `/processos` cru.** Ele ainda alimenta as views de Intimações,
   Prazos, Petições, as opções de filtro e os modais (`page.tsx` linhas 329,
   406, 514, 546, 951, 1319, 1330). O endpoint novo é **aditivo**.
4. **Busca e filtros continuam client-side e instantâneos**, agora sobre linhas
   completas e corretas.
5. **Campos de paridade de busca** (`intimacao_tipo`/`peticao_tipo`) são
   mantidos para não regredir silenciosamente a busca atual.
6. **Sem paginação server-side agora.** O formato da resposta (`{ total, items }`)
   é escolhido para que, quando passar do conforto de uma carga só, o mesmo
   endpoint só ganhe `limit/offset/q` sem trocar o contrato.

## 1. Endpoint — `GET /processos/resumo`

Resposta:

```
ProcessoResumoLista {
  total: int                    # COUNT(*) real de processos do tenant
  items: ProcessoResumo[]
}

ProcessoResumo {
  id: int
  numero: str
  classe: str | null
  tribunal: str | null
  orgao_julgador: str | null
  sistema: str | null
  intimacoes_count: int
  peticoes_count: int
  proximo_prazo: ProximoPrazo | null    # menor data_fatal pendente
  intimacao_tipo: str | null            # tipo_comunicacao da intimação mais recente
  peticao_tipo: str | null              # tipo da petição mais recente
}

ProximoPrazo {
  data_fatal: date
  cumprido: bool          # sempre false aqui, mas mantido p/ compat com DeadlineBadge/risco
  descricao: str | null
}
```

- `total` é a fonte de verdade do número do cabeçalho — **nunca mais mente**.
- Tenant-scoped via `tenant_select(models.Processo, current)` (mesma população
  que o card `processos` do `/dashboard/operational`, então os dois batem).
- Ordenação dos `items`: `Processo.id.desc()` (igual ao `/processos` cru).
- Cap defensivo interno (ex.: 5000). Como 5000 > 3k alvo, na prática
  `len(items) == total`. Se um dia `total > cap`, ver §3 (guarda de honestidade)
  e §5.

Schema Pydantic novo em `backend/app/api/schemas.py`
(`ProcessoResumoOut` + `ProximoPrazoOut` + `ProcessoResumoLista`).

## 2. Estratégia de query (sem N+1, agnóstica de DB)

Mesmo padrão que o `/review/queue` já usa (dicts montados em Python). Custo fixo
(~4-5 queries) independente de 200 ou 3.000 processos:

1. `processos = tenant_select(Processo).order_by(id.desc())` → 6 campos + base do
   `total` (`len` ou `COUNT(*)`).
2. `SELECT processo_id, COUNT(*) FROM intimacao WHERE <tenant> GROUP BY
   processo_id` → `intimacoes_count` por processo (dict).
3. Idem em `peticao` → `peticoes_count` (dict).
4. Prazos pendentes: `tenant_select(Prazo).where(cumprido == False)
   .order_by(data_fatal.asc())`; primeiro por `processo_id` em Python →
   `proximo_prazo` (data_fatal, cumprido=False, descricao).
5. `intimacao_tipo`/`peticao_tipo`: mais recente por processo, montado na
   costura. "Mais recente" = maior `Intimacao.data_disponibilizacao` (mesma
   ordenação de `/intimacoes`) e maior `Peticao.id` (mesma ordenação de
   `/peticoes`).

Stitch final: para cada processo, monta o `ProcessoResumo` puxando dos dicts
(default 0 / None quando ausente).

Nota de eficiência (fora de escopo, registrada): o card `processos` do
`/dashboard/operational` conta via `len(...all())` (carrega todas as linhas só
pra contar). Poderia virar `COUNT(*)`. Não faz parte deste spec.

## 3. Frontend

- **`lib/api.ts`**: novo tipo `ProcessoResumo`/`ProcessoResumoLista` e
  `loadDashboard` passa a **também** buscar `/processos/resumo` (via
  `requestOptional`/`requestList`, com fallback vazio). As outras 4 listas seguem
  carregando para as demais views. O `data.processos` cru permanece.
- **`page.tsx`**: `processoRows` deixa de ser o join de 4 tabelas
  (`processosPool`/`prazosPool`) e passa a ser derivado dos `items` do endpoint.
  O `mergeById` para a view de Processos deixa de ser necessário (permanece para
  Prazos, que ainda usa `prazosPool`).
- **Busca (`matchesQuery`)**: passa a ler dos campos enriquecidos —
  `proximo_prazo.descricao`, `intimacao_tipo`, `peticao_tipo` — em vez de
  `proximoPrazo?.descricao`, `intimacoes[0]?.tipo_comunicacao`,
  `peticoes[0]?.tipo`.
- **Filtro (`passesFilters`)**: `tribunal`, `sistema` e `risco` derivado de
  `proximo_prazo` (`riscoFromDias(daysUntil(proximo_prazo.data_fatal),
  proximo_prazo.cumprido)`).
- **Opções de filtro** da view de Processos derivam dos `items` (não do
  `data.processos` capado).
- **`ProcessosView.tsx`**: consome a nova forma de linha. `intimacoes.length` →
  `intimacoes_count`; `peticoes.length` → `peticoes_count`; `proximoPrazo` →
  `proximo_prazo` (mesmos campos que o `DeadlineBadge` usa: `data_fatal`,
  `cumprido`).
- **Export CSV**: lê `intimacoes_count`, `peticoes_count`,
  `proximo_prazo?.data_fatal`.
- **Paginação client-side da tabela**: página de ~50 linhas (prev/próxima) para
  3k linhas não pesarem o DOM. Sem envolvimento do servidor.
- **Cabeçalho**: `viewCount` da view de Processos = `total`.
- **Guarda de honestidade**: se `items.length < total`, a UI mostra "exibindo X
  de Y" em vez de fingir o total. Impede a reincidência do bug original.

## 4. Testes

**Backend (`backend/tests/test_api.py`)**
- `intimacoes_count`/`peticoes_count` corretos por processo.
- `proximo_prazo` = menor `data_fatal` entre os pendentes; `null` quando não há
  pendente (ignora cumpridos).
- `total` == número de processos do tenant.
- **Isolamento de tenant**: processo/intimação/prazo de outro escritório não
  vaza na contagem nem nos itens.
- `intimacao_tipo`/`peticao_tipo` = do registro mais recente.

**Frontend**
- `api.test.ts`: `loadDashboard` chama `/processos/resumo`.
- Montagem de `processoRows` a partir dos `items` (contagens e próximo prazo
  corretos).
- Paridade: `viewCount` da view de Processos == `total`.
- Busca e filtros funcionando sobre os campos enriquecidos.
- Guarda "X de Y" quando `items.length < total`.

## 5. Escopo e evolução futura

- **Fora de escopo:** Intimações, Prazos, Petições (mesmo padrão, depois);
  `COUNT(*)` no card do dashboard.
- **Quando passar do conforto de carga única (> ~3-5k):** o endpoint ganha
  `limit`, `offset` e `q` (busca server-side), a tabela vira paginada de
  verdade, e a busca/filtro migram pro servidor. O contrato `{ total, items }`
  não muda — por isso essa forma foi escolhida agora.
