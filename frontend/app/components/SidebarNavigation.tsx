"use client";

import { BookOpen, CheckCircle2, Clock3, FilePenLine, HomeIcon, Inbox, ListTodo, MessageCircle, Scale, Send, ShieldCheck, Table2, Users, Workflow } from "lucide-react";
import { NAV_GROUPS } from "@/lib/navigation";
import { VIEW_LABEL, type ViewKey } from "@/lib/views";
import { NavGroup, NavItem } from "./ui";

const ICONS = { dashboard: HomeIcon, tarefas: ListTodo, intimacoes: Inbox, prazos: Clock3,
  clientes: Users, processos: Scale, assistente: MessageCircle, peticoes: FilePenLine, templates: BookOpen,
  gate: ShieldCheck, protocolos: Send, conectores: Workflow, auditoria: Table2, onboarding: CheckCircle2 };

export default function SidebarNavigation({ view, onNavigate }: { view: ViewKey; onNavigate: (view: ViewKey) => void }) {
  return <nav className="sideNav" aria-label="Módulos do Causor">
    {NAV_GROUPS.map(group => <NavGroup key={group.label} label={group.label}>
      {group.items.map(key => {
        const Icon = ICONS[key];
        return <NavItem key={key} icon={<Icon size={17} />} label={VIEW_LABEL[key]} active={view === key} onClick={() => onNavigate(key)} />;
      })}
    </NavGroup>)}
  </nav>;
}
