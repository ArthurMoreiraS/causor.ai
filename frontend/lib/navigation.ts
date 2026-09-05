import type { ViewKey } from "./views";

/** Only functioning destinations belong in the menu; future modules live in the product plan. */
export const NAV_GROUPS: { label: string; items: ViewKey[] }[] = [
  { label: "Trabalho diário", items: ["dashboard", "tarefas", "intimacoes", "prazos"] },
  { label: "Escritório", items: ["clientes", "processos", "documentos"] },
  { label: "Produção jurídica", items: ["assistente", "peticoes", "templates", "gate", "protocolos"] },
  { label: "Administração", items: ["conectores", "auditoria", "onboarding"] }
];

export function viewFromHash(hash: string): ViewKey {
  const value = hash.replace(/^#/, "");
  return NAV_GROUPS.flatMap(group => group.items).find(view => view === value) ?? "dashboard";
}
