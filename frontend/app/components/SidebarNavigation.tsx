"use client";

import { BookOpen, BriefcaseBusiness, CheckCircle2, Clock3, FilePenLine, HomeIcon, Inbox, ListTodo, MessageCircle, Plus, Scale, Send, ShieldCheck, Table2, Users, Workflow } from "lucide-react";
import { NAV_GROUPS } from "@/lib/navigation";
import { Fragment } from "react";
import { VIEW_LABEL, type ViewKey } from "@/lib/views";
import { NavGroup, NavItem } from "./ui";

const ICONS = { dashboard: HomeIcon, tarefas: ListTodo, trabalhos: BriefcaseBusiness, intimacoes: Inbox, prazos: Clock3,
  clientes: Users, processos: Scale, documentos: BookOpen, assistente: MessageCircle, peticoes: FilePenLine, templates: BookOpen,
  gate: ShieldCheck, protocolos: Send, conectores: Workflow, auditoria: Table2, onboarding: CheckCircle2 };

export default function SidebarNavigation({ view, onNavigate, onNewWork }: { view: ViewKey; onNavigate: (view: ViewKey) => void; onNewWork?: () => void }) {
  return <nav className="sideNav" aria-label="Módulos do Causor">
    {NAV_GROUPS.map(group => <NavGroup key={group.label} label={group.label}>
      {group.items.map(key => {
        const Icon = ICONS[key];
        return <Fragment key={key}><NavItem icon={<Icon size={17} />} label={VIEW_LABEL[key]} active={view === key} onClick={() => onNavigate(key)} />
          {key === "trabalhos" && onNewWork ? <NavItem icon={<Plus size={17} />} label="Novo trabalho" onClick={onNewWork} /> : null}</Fragment>;
      })}
    </NavGroup>)}
  </nav>;
}
