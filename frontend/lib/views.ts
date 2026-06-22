import type { Intimacao, Peticao, Prazo, Processo } from "@/lib/api";

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

/** Linhas agregadas usadas pelas views (SOR cruzado no cliente). */
export type ProcessoRow = {
  processo: Processo;
  prazos: Prazo[];
  intimacoes: Intimacao[];
  peticoes: Peticao[];
  proximoPrazo: Prazo | null;
};

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
