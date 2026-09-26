import type { ViewKey } from "./views";

/** MVP: show the case intake, context, drafting, and human review path. */
export const NAV_GROUPS: { label: string; items: ViewKey[] }[] = [
  { label: "Trabalho diário", items: ["dashboard", "tarefas", "intimacoes", "prazos"] },
  { label: "Escritório", items: ["clientes", "processos", "documentos", "assistente"] },
  { label: "Produção jurídica", items: ["trabalhos", "peticoes", "templates", "gate"] },
  { label: "Administração", items: ["auditoria", "onboarding"] }
];

export function viewFromHash(hash: string): ViewKey {
  const value = hash.replace(/^#/, "");
  return NAV_GROUPS.flatMap(group => group.items).find(view => view === value) ?? "dashboard";
}
