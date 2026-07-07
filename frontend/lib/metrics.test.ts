import { describe, expect, it } from "vitest";
import type { DashboardData, DashboardMetric, Intimacao, Peticao, Prazo, Processo } from "@/lib/api";
import { computeDashboardMetrics } from "./metrics";

function processo(id: number): Processo {
  return { id, numero: String(id), classe: null, tribunal: "TJSP", orgao_julgador: null, sistema: null };
}

function intimacao(id: number, processoId: number | null): Intimacao {
  return {
    id,
    processo_id: processoId,
    fonte: "DJEN",
    numero_processo: "0000001-00.2024.8.26.0100",
    tribunal: "TJSP",
    tipo_comunicacao: "Intimação",
    teor: "",
    data_disponibilizacao: "2024-09-06",
    data_publicacao: "2024-09-06"
  };
}

function prazo(id: number, dataFatal: string, cumprido = false): Prazo {
  return {
    id,
    processo_id: 1,
    intimacao_id: id,
    descricao: null,
    data_inicio: "2024-09-09",
    dias: 15,
    dias_uteis: true,
    data_fatal: dataFatal,
    cumprido
  };
}

function peticao(id: number, status: Peticao["status"]): Peticao {
  return { id, processo_id: 1, prazo_id: null, tipo: null, conteudo: null, dossie: null, status, aprovada_por: null, protocolada_em: null };
}

function metric(key: string, value: number): DashboardMetric {
  return { key, label: key, value };
}

function makeData(over: Partial<DashboardData> = {}): DashboardData {
  return { intimacoes: [], processos: [], prazos: [], peticoes: [], ...over };
}

describe("computeDashboardMetrics", () => {
  it("usa as contagens reais do /dashboard/operational em vez do tamanho das listas paginadas", () => {
    // As listas vêm capadas em limit=100 pela API; operational traz o total real.
    const data = makeData({
      processos: Array.from({ length: 100 }, (_, i) => processo(i + 1)),
      intimacoes: Array.from({ length: 100 }, (_, i) => intimacao(i + 1, 1)),
      prazos: Array.from({ length: 100 }, (_, i) => prazo(i + 1, "2999-01-01")),
      operational: {
        metrics: [
          metric("processos", 250),
          metric("intimacoes", 340),
          metric("prazos", 180),
          metric("risco", 12),
          metric("vencidos", 7),
          metric("minutas", 5),
          metric("aprovadas", 3)
        ],
        workflow: [],
        connectors: [],
        audit_signals: []
      }
    });

    const m = computeDashboardMetrics(data);

    expect(m.monitored).toBe(250);
    expect(m.captured).toBe(340);
    expect(m.pending).toBe(180);
    expect(m.highRisk).toBe(12);
    expect(m.overdue).toBe(7);
    expect(m.drafts).toBe(5);
    expect(m.approved).toBe(3);
    // compliance derivado de pending/overdue: round((180-7)/180*100) = 96
    expect(m.compliance).toBe(96);
  });

  it("cai para a contagem das listas quando /dashboard/operational está indisponível", () => {
    const data = makeData({
      processos: [processo(1), processo(2)],
      intimacoes: [intimacao(1, 1)],
      prazos: [prazo(1, "2999-01-01"), prazo(2, "2000-01-01"), prazo(3, "2999-01-01", true)],
      peticoes: [peticao(1, "rascunho"), peticao(2, "aprovada")]
      // sem operational -> fallback client-side
    });

    const m = computeDashboardMetrics(data);

    expect(m.monitored).toBe(2);
    expect(m.captured).toBe(1);
    expect(m.pending).toBe(2); // 2 não cumpridos
    expect(m.overdue).toBe(1); // o com data_fatal em 2000
    expect(m.drafts).toBe(1);
    expect(m.approved).toBe(1);
    expect(m.compliance).toBe(50); // round((2-1)/2*100)
  });

  it("respeita valor 0 vindo do operational em vez de cair para o fallback das listas", () => {
    const data = makeData({
      prazos: [prazo(1, "2000-01-01")], // fallback de overdue seria 1
      operational: {
        metrics: [metric("prazos", 0), metric("vencidos", 0)],
        workflow: [],
        connectors: [],
        audit_signals: []
      }
    });

    const m = computeDashboardMetrics(data);

    expect(m.pending).toBe(0);
    expect(m.overdue).toBe(0);
    expect(m.compliance).toBe(100); // pending 0 -> 100
  });
});
