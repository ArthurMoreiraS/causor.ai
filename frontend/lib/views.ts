import type { Intimacao, Peticao, Prazo, Processo } from "@/lib/api";

export type ViewKey =
  | "fila"
  | "inicio"
  | "assistente"
  | "operacao"
  | "processos"
  | "intimacoes"
  | "prazos"
  | "peticoes"
  | "templates"
  | "gate"
  | "auditoria";

export type StatusKey = "pendentes" | "minutadas" | "aprovadas" | "protocoladas";

export const STATUS_MATCH: Record<StatusKey, (status: string) => boolean> = {
  pendentes: (s) => s !== "protocolada" && s !== "cumprido",
  minutadas: (s) => s === "minuta_em_revisao",
  aprovadas: (s) => s === "pronta_para_protocolo",
  protocoladas: (s) => s === "protocolada"
};

export const VIEW_LABEL: Record<ViewKey, string> = {
  fila: "Fila do dia",
  templates: "Minutas & Templates",
  inicio: "Central de Comando",
  assistente: "Assistente Causor",
  operacao: "Agente de Operações Processuais",
  processos: "Processos",
  intimacoes: "Intimações",
  prazos: "Prazos",
  peticoes: "Minutas",
  gate: "Gate OAB",
  auditoria: "Auditoria"
};

export const EMPTY_BY_VIEW: Record<ViewKey, string> = {
  fila: "Fila vazia — nenhum ato pendente",
  templates: "Nenhum template cadastrado",
  inicio: "Nenhuma prioridade encontrada",
  assistente: "Nenhuma conversa iniciada",
  operacao: "Nenhuma intimação encontrada",
  processos: "Nenhum processo encontrado",
  intimacoes: "Nenhuma intimação encontrada",
  prazos: "Nenhum prazo encontrado",
  peticoes: "Nenhuma minuta encontrada",
  gate: "Nenhum item no gate OAB",
  auditoria: "Sem eventos de auditoria"
};

export const VIEW_COPY: Record<ViewKey, string> = {
  fila: "Tudo que precisa de ação hoje, do mais crítico ao mais tranquilo.",
  templates: "Modelos do escritório que estruturam a redação das minutas.",
  inicio: "Visão executiva do piloto: prioridades, risco e próximos atos.",
  assistente: "Converse com o agente, consulte o SOR e confirme ações com gate humano.",
  operacao: "Fila integrada de captura, prazo, minuta e gate humano.",
  processos: "Registro dos processos monitorados e seus próximos riscos.",
  intimacoes: "Inbox operacional das comunicações capturadas no DJEN.",
  prazos: "Lista operacional de prazos com revisão e baixa.",
  peticoes: "Ambiente de minuta e revisão de conteúdo antes do gate.",
  gate: "Fila de aprovação humana e protocolo assistido com responsabilidade OAB.",
  auditoria: "Trilha imutável dos atos executados pelo sistema."
};

export const WORKFLOW_FALLBACK = [
  { key: "capture", label: "Captura", detail: "DJEN + DataJud", status: "live" },
  { key: "deadline", label: "Prazo", detail: "Motor determinístico", status: "live" },
  { key: "draft", label: "Minuta", detail: "Claude + templates", status: "review" },
  { key: "approval", label: "Aprovação", detail: "Gate OAB", status: "review" },
  { key: "filing", label: "Protocolo", detail: "PJe / e-SAJ", status: "next" }
];

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
