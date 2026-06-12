"use client";

import { ChevronDown, UserRound } from "lucide-react";
import type { ReactNode } from "react";
import type { Prazo } from "@/lib/api";
import { daysUntil } from "@/lib/format";

export function NavGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="navGroup">
      <div className="navGroupLabel">
        <span>{label}</span>
        <ChevronDown size={12} />
      </div>
      {children}
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

export function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function AmountCard({ label, value, detail }: { label: string; value: number; detail: string }) {
  return (
    <article className="amountCard">
      <span>{label}</span>
      <strong>{value.toLocaleString("pt-BR")}</strong>
      <small>{detail}</small>
    </article>
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

export function AuditItem({ icon, title, detail }: { icon: ReactNode; title: string; detail: string }) {
  return (
    <article className="auditItem">
      <div className="auditIcon">{icon}</div>
      <div>
        <strong>{title}</strong>
        <span>{detail}</span>
      </div>
    </article>
  );
}

export function Empty({ label }: { label: string }) {
  return (
    <div className="empty">
      <UserRound size={18} />
      <span>{label}</span>
    </div>
  );
}
