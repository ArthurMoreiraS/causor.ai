import type {
  Intimacao,
  Peticao,
  Prazo,
  Processo,
  ProcessoResumoLista,
  ProximoPrazo,
  ReviewQueueItem
} from "@/lib/api";

export type ViewKey =
  | "dashboard"
  | "onboarding"
  | "assistente"
  | "processos"
  | "intimacoes"
  | "prazos"
  | "peticoes"
  | "templates"
  | "gate"
  | "protocolos"
  | "conectores"
  | "auditoria";

export type StatusKey = "pendentes" | "minutadas" | "aprovadas" | "protocoladas";

export const STATUS_MATCH: Record<StatusKey, (status: string) => boolean> = {
  pendentes: (s) => s !== "protocolada" && s !== "cumprido",
  minutadas: (s) => s === "minuta_em_revisao",
  aprovadas: (s) => s === "pronta_para_protocolo",
  protocoladas: (s) => s === "protocolada"
};

export const VIEW_LABEL: Record<ViewKey, string> = {
  dashboard: "Dashboard",
  onboarding: "Onboarding",
  templates: "Minutas & Templates",
  assistente: "Assistente Causor",
  processos: "Processos",
  intimacoes: "Intimações",
  prazos: "Prazos",
  peticoes: "Minutas",
  gate: "Gate OAB",
  protocolos: "Protocolos",
  conectores: "Conectores",
  auditoria: "Auditoria"
};

export const CONNECTORS_FALLBACK = [
  { key: "djen", name: "DJEN", detail: "captura oficial", status: "online" },
  { key: "datajud", name: "DataJud", detail: "andamentos e metadados", status: "online" },
  { key: "pje", name: "PJe", detail: "protocolo assistido", status: "pilot" },
  { key: "esaj", name: "e-SAJ", detail: "próximo conector", status: "planned" }
];

/** Linha da view de Processos: processo + próximo prazo + contagens + tipos
 * representativos. Vem cruzada do servidor (`/processos/resumo`); o fallback
 * client-side produz o mesmo formato quando o endpoint está indisponível. */
export type ProcessoRow = {
  processo: Processo;
  proximoPrazo: ProximoPrazo | null;
  intimacoesCount: number;
  peticoesCount: number;
  intimacaoTipo: string | null;
  peticaoTipo: string | null;
};

/** Linhas da view de Processos a partir do endpoint enriquecido — sem re-cruzar
 * listas paginadas no cliente (a origem do descasamento 200 vs 195). */
export function buildProcessoRows(resumo: ProcessoResumoLista): ProcessoRow[] {
  return resumo.items.map((item) => ({
    processo: {
      id: item.id,
      numero: item.numero,
      classe: item.classe,
      tribunal: item.tribunal,
      orgao_julgador: item.orgao_julgador,
      sistema: item.sistema
    },
    proximoPrazo: item.proximo_prazo,
    intimacoesCount: item.intimacoes_count,
    peticoesCount: item.peticoes_count,
    intimacaoTipo: item.intimacao_tipo,
    peticaoTipo: item.peticao_tipo
  }));
}

/** Fallback: monta as mesmas linhas cruzando as listas no cliente, usado só
 * quando `/processos/resumo` não responde (backend antigo/offline). Sujeito ao
 * teto de paginação das listas — por isso é fallback, não o caminho principal. */
export function buildProcessoRowsFromLists(
  processos: Processo[],
  prazos: Prazo[],
  intimacoes: Intimacao[],
  peticoes: Peticao[]
): ProcessoRow[] {
  return processos.map((processo) => {
    const procIntimacoes = intimacoes.filter((i) => i.processo_id === processo.id);
    const procPeticoes = peticoes.filter((p) => p.processo_id === processo.id);
    const proximo =
      prazos
        .filter((p) => p.processo_id === processo.id && !p.cumprido)
        .sort(
          (a, b) => new Date(a.data_fatal).getTime() - new Date(b.data_fatal).getTime()
        )[0] ?? null;
    return {
      processo,
      proximoPrazo: proximo
        ? { data_fatal: proximo.data_fatal, cumprido: proximo.cumprido, descricao: proximo.descricao }
        : null,
      intimacoesCount: procIntimacoes.length,
      peticoesCount: procPeticoes.length,
      intimacaoTipo: procIntimacoes[0]?.tipo_comunicacao ?? null,
      peticaoTipo: procPeticoes[0]?.tipo ?? null
    };
  });
}

export type IntimacaoRow = {
  intimacao: Intimacao;
  processo: Processo | null;
  prazo: Prazo | null;
  peticao: Peticao | null;
};

export type PrazoRow = {
  prazo: Prazo;
  processo: Processo | null;
  intimacao: Intimacao | null;
  peticao: Peticao | null;
  dias: number;
};

export type PeticaoRow = {
  peticao: Peticao;
  processo: Processo | null;
  prazo: Prazo | null;
};

/**
 * Linhas de intimação a partir da fila de revisão do servidor (`/review/queue`),
 * que já cruza intimação → prazo → processo → petição corretamente. Antes o
 * cliente re-cruzava contra `/prazos` (paginado por fatal mais antiga), então
 * intimações recentes não achavam seu prazo e apareciam como "Pendente" mesmo
 * tendo prazo. Derivar do reviewQueue elimina esse descasamento de paginação.
 */
export function buildIntimacaoRows(queue: ReviewQueueItem[]): IntimacaoRow[] {
  return queue.map((item) => ({
    intimacao: item.intimacao,
    processo: item.processo,
    prazo: item.prazo,
    peticao: item.peticao
  }));
}

/**
 * União por `id` de duas listas de entidades, mantendo a base em conflito e
 * ignorando nulos. Usada para completar os pools de prazos/processos com as
 * entidades já cruzadas pelo reviewQueue — que podem estar fora da página
 * separadamente limitada de `/prazos` e `/processos` — antes dos joins das
 * views de Prazos e Processos.
 */
export function mergeById<T extends { id: number }>(
  base: T[],
  extra: Array<T | null | undefined>
): T[] {
  const byId = new Map<number, T>();
  for (const item of base) byId.set(item.id, item);
  for (const item of extra) {
    if (item && !byId.has(item.id)) byId.set(item.id, item);
  }
  return Array.from(byId.values());
}
