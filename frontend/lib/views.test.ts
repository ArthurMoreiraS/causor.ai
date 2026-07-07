import { describe, expect, it } from "vitest";
import type { Intimacao, Prazo, Processo, ReviewQueueItem } from "@/lib/api";
import { buildIntimacaoRows, mergeById } from "./views";

function intimacao(id: number, processoId: number | null): Intimacao {
  return {
    id,
    processo_id: processoId,
    fonte: "DJEN",
    numero_processo: "0000001-00.2024.8.26.0100",
    tribunal: "TJSP",
    tipo_comunicacao: "Intimação",
    teor: "Manifeste-se em 15 dias.",
    data_disponibilizacao: "2024-09-06",
    data_publicacao: "2024-09-06"
  };
}

function prazo(id: number, intimacaoId: number, processoId: number | null): Prazo {
  return {
    id,
    processo_id: processoId,
    intimacao_id: intimacaoId,
    descricao: "Provisório",
    data_inicio: "2024-09-09",
    dias: 15,
    dias_uteis: true,
    data_fatal: "2024-09-30",
    cumprido: false
  };
}

function processo(id: number): Processo {
  return { id, numero: "00000010020248260100", classe: null, tribunal: "TJSP", orgao_julgador: null, sistema: null };
}

function queueItem(item: Partial<ReviewQueueItem> & { intimacao: Intimacao }): ReviewQueueItem {
  return {
    processo: null,
    prazo: null,
    peticao: null,
    status: "prazo_calculado",
    risco: "vencido",
    dias_para_vencer: -5,
    ...item
  };
}

describe("buildIntimacaoRows", () => {
  it("carrega o prazo vinculado no servidor mesmo fora da página limitada de /prazos", () => {
    // Regressão do bug de paginação: a intimação recente tem prazo, mas com o
    // join client-side contra /prazos (limitado às fatais mais antigas) ela
    // aparecia como "Pendente". Derivando do reviewQueue, o prazo vem junto.
    const it10 = intimacao(10, 5);
    const pz99 = prazo(99, 10, 5);
    const rows = buildIntimacaoRows([queueItem({ intimacao: it10, processo: processo(5), prazo: pz99 })]);

    expect(rows).toHaveLength(1);
    expect(rows[0].prazo).toEqual(pz99); // não é null -> DeadlineBadge não mostra "Pendente"
    expect(rows[0].intimacao).toEqual(it10);
    expect(rows[0].processo?.id).toBe(5);
  });

  it("mantém prazo null quando a intimação realmente não tem prazo", () => {
    const rows = buildIntimacaoRows([queueItem({ intimacao: intimacao(11, null), prazo: null })]);
    expect(rows[0].prazo).toBeNull();
  });
});

describe("mergeById", () => {
  it("faz união por id, mantém a base em caso de conflito e ignora nulos", () => {
    const base = processo(1);
    const dup = { ...processo(1), tribunal: "OUTRO" };
    const extra = processo(2);

    const merged = mergeById<Processo>([base], [dup, extra, null]);

    expect(merged.map((p) => p.id)).toEqual([1, 2]);
    expect(merged.find((p) => p.id === 1)?.tribunal).toBe("TJSP"); // base vence
  });
});
