"use client";

import { ChevronDown, UserRound } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import type { Prazo } from "@/lib/api";
import { daysUntil } from "@/lib/format";

export function NavGroup({ label, children }: { label: string; children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <div className={`navGroup${collapsed ? " collapsed" : ""}`}>
      <button
        type="button"
        className="navGroupLabel"
        aria-expanded={!collapsed}
        onClick={() => setCollapsed((value) => !value)}
      >
        <span>{label}</span>
        <ChevronDown size={12} />
      </button>
      {collapsed ? null : children}
    </div>
  );
}

export function NavItem({
  icon,
  label,
  active = false,
  onClick
}: {
  icon: ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <a
      className={active ? "active" : ""}
      href="#"
      title={label}
      onClick={(e) => {
        e.preventDefault();
        onClick?.();
      }}
    >
      {icon}
      <span>{label}</span>
    </a>
  );
}

export function Panel({
  title,
  action,
  children
}: {
  title: string;
  action: string;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <header>
        <h2>{title}</h2>
        <span>{action}</span>
      </header>
      {children}
    </section>
  );
}

export function CommandStat({ label, value, detail }: { label: string; value: ReactNode; detail: string }) {
  return (
    <article className="commandStat">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

export function FeatureTile({
  icon,
  label,
  value,
  onClick
}: {
  icon: ReactNode;
  label: string;
  value: number;
  onClick: () => void;
}) {
  return (
    <button className="featureTile" onClick={onClick}>
      <span>{icon}</span>
      <strong>{label}</strong>
      <small>{value}</small>
    </button>
  );
}

export function DeadlineBadge({ prazo }: { prazo: Prazo | null | undefined }) {
  if (!prazo) return <span className="dayBadge neutral">Pendente</span>;
  const remaining = daysUntil(prazo.data_fatal);
  if (prazo.cumprido) return <span className="dayBadge done">Concluído</span>;
  if (remaining <= 0) return <span className="dayBadge risk">Vencido</span>;
  if (remaining <= 3) return <span className="dayBadge today">{remaining}d</span>;
  return <span className="dayBadge neutral">{remaining}d</span>;
}

export function Empty({ label }: { label: string }) {
  return (
    <div className="empty">
      <UserRound size={18} />
      <span>{label}</span>
    </div>
  );
}
