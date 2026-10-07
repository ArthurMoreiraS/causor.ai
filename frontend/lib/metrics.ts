import type { DashboardData } from "@/lib/api";
import { daysUntil, isPrazoVigente } from "./format";

export type DashboardMetrics = {
  monitored: number;
  captured: number;
  pending: number;
  reviewPending: number;
  confirmedPending: number;
  highRisk: number;
  overdue: number;
  drafts: number;
  approved: number;
  withoutDraft: number;
  compliance: number;
};

/**
 * Números do dashboard. A fonte de verdade é `/dashboard/operational`, que conta
 * no servidor sem o teto de `limit=100` das listas paginadas. Contar `.length`
 * das listas capava tudo em 100 — os cards mostravam "100, 100, 100" mesmo com
 * milhares de registros. As listas ficam só como fallback quando o endpoint
 * operacional está indisponível (é opcional em `loadDashboard`).
 */
export function computeDashboardMetrics(data: DashboardData): DashboardMetrics {
  const openDeadlines = data.prazos.filter((p) => !p.cumprido);
  // Vigente: confirmado ou calculado automaticamente (vale sem conferência).
  const confirmedDeadlines = openDeadlines.filter((p) => isPrazoVigente(p.revisao_status));

  // Fallback client-side, derivado das listas paginadas (capadas em 100).
  const fromLists = {
    monitored: data.processos.length,
    captured: data.intimacoes.length,
    pending: openDeadlines.length,
    reviewPending: openDeadlines.length - confirmedDeadlines.length,
    confirmedPending: confirmedDeadlines.length,
    highRisk: confirmedDeadlines.filter((p) => daysUntil(p.data_fatal) <= 3).length,
    overdue: confirmedDeadlines.filter((p) => daysUntil(p.data_fatal) < 0).length,
    drafts: data.peticoes.filter((p) => p.status === "rascunho").length,
    approved: data.peticoes.filter((p) => p.status === "aprovada").length
  };

  const op = new Map(data.operational?.metrics.map((m) => [m.key, m.value]));
  // `?? fb` só cai no fallback em ausência (undefined); um 0 real do servidor é preservado.
  const pick = (key: string, fb: number) => op.get(key) ?? fb;

  const monitored = pick("processos", fromLists.monitored);
  const captured = pick("intimacoes", fromLists.captured);
  const pending = pick("prazos", fromLists.pending);
  const reviewPending = pick("prazos_a_revisar", fromLists.reviewPending);
  const confirmedPending = Math.max(0, pending - reviewPending);
  const highRisk = pick("risco", fromLists.highRisk);
  const overdue = pick("vencidos", fromLists.overdue);
  const drafts = pick("minutas", fromLists.drafts);
  const approved = pick("aprovadas", fromLists.approved);

  // Sem equivalente no operational e não exibido nos cards — segue client-side.
  const handledProcessos = new Set(data.peticoes.map((p) => p.processo_id));
  const withoutDraft = data.intimacoes.filter(
    (i) => !i.processo_id || !handledProcessos.has(i.processo_id)
  ).length;

  const compliance = confirmedPending ? Math.round(((confirmedPending - overdue) / confirmedPending) * 100) : 100;

  return { monitored, captured, pending, reviewPending, confirmedPending, highRisk, overdue, drafts, approved, withoutDraft, compliance };
}
