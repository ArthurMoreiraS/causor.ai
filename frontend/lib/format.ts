import type { Peticao } from "@/lib/api";

export function formatDate(value: string | null | undefined) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(value));
}

export function daysUntil(value: string) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(value);
  target.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - today.getTime()) / 86_400_000);
}

export function statusLabel(status: Peticao["status"]) {
  if (status === "rascunho") return "Rascunho";
  if (status === "em_revisao") return "Em revisão";
  if (status === "aprovada") return "Aprovada";
  if (status === "protocolada") return "Protocolada";
  return status;
}

export function sistemaBadge(sistema: string | null | undefined): { label: string; className: string } {
  if (!sistema) return { label: "Sistema não identificado", className: "sistemaDesconhecido" };
  if (sistema.trim().toLowerCase() === "pje") {
    return { label: "PJe · protocolo automatizado", className: "sistemaPje" };
  }
  return { label: `${sistema} · protocolo manual`, className: "sistemaOutro" };
}

export function connectorStatusLabel(status: string) {
  if (status === "online") return "ativo";
  if (status === "pilot") return "piloto";
  if (status === "planned") return "planejado";
  if (status === "live") return "ativo";
  if (status === "review") return "revisão";
  return status;
}

export function reviewStatusLabel(status: string) {
  if (status === "capturada") return "Capturada";
  if (status === "prazo_calculado") return "Prazo calculado";
  if (status === "minuta_em_revisao") return "Minuta em revisão";
  if (status === "pronta_para_protocolo") return "Pronta para protocolo";
  if (status === "protocolada") return "Protocolada";
  if (status === "cumprido") return "Cumprido";
  return status;
}

export function riskLabel(risco: string) {
  if (risco === "vencido") return "Vencido";
  if (risco === "alto") return "Alto";
  if (risco === "baixo") return "Baixo";
  if (risco === "cumprido") return "Cumprido";
  return "Sem prazo";
}

export function matchesQuery(values: Array<string | number | null | undefined>, query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;
  return values
    .filter((value) => value !== null && value !== undefined)
    .some((value) => String(value).toLowerCase().includes(normalized));
}

export type FilterState = { tribunal: string; sistema: string; risco: string };

export function riscoFromDias(dias: number | null, cumprido?: boolean): string {
  if (cumprido) return "cumprido";
  if (dias === null) return "sem_prazo";
  if (dias < 0) return "vencido";
  if (dias <= 3) return "alto";
  if (dias <= 7) return "medio";
  return "baixo";
}

export function passesFilters(
  filters: FilterState,
  fields: { tribunal?: string | null; sistema?: string | null; risco?: string | null }
) {
  if (filters.tribunal && fields.tribunal !== filters.tribunal) return false;
  if (filters.sistema && fields.sistema !== filters.sistema) return false;
  if (filters.risco && fields.risco !== filters.risco) return false;
  return true;
}
