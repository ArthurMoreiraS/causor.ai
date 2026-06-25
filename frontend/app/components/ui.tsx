"use client";

import { AlertCircle, ChevronDown, Inbox, Info, Loader2, Moon, RefreshCw, Sun, UserRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from "react";
import type { Prazo } from "@/lib/api";
import { daysUntil } from "@/lib/format";

/** Placeholder de carregamento com shimmer. Usa tokens do design system. */
export function Skeleton({
  width = "100%",
  height = 14,
  radius,
  className
}: {
  width?: number | string;
  height?: number | string;
  radius?: number | string;
  className?: string;
}) {
  const style: CSSProperties = { width, height };
  if (radius !== undefined) style.borderRadius = radius;
  return <span className={className ? `skeleton ${className}` : "skeleton"} style={style} aria-hidden="true" />;
}

/** Linhas de texto em skeleton (a última mais curta). */
export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <span className="skeletonGroup" aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} height={12} width={i === lines - 1 ? "60%" : "100%"} />
      ))}
    </span>
  );
}

/** Botão que mostra spinner e fica desabilitado durante uma ação assíncrona. */
export function LoadingButton({
  loading = false,
  icon,
  iconSize = 14,
  className,
  disabled,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  loading?: boolean;
  icon?: ReactNode;
  iconSize?: number;
}) {
  return (
    <button
      className={className ?? "toolbarButton"}
      disabled={loading || disabled}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Loader2 className="spin" size={iconSize} /> : icon}
      {children}
    </button>
  );
}

/** Ícone informacional com tooltip acessível (hover + foco de teclado). */
export function InfoHint({ label }: { label: string }) {
  return (
    <span className="infoHint" tabIndex={0} role="note" aria-label={label}>
      <Info size={13} aria-hidden="true" />
      <span className="infoHintBubble" aria-hidden="true">
        {label}
      </span>
    </span>
  );
}

/** Estado vazio padronizado: ícone + título + descrição + ação opcional. */
export function EmptyState({
  icon,
  title,
  description,
  action
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="stateBlock">
      <span className="stateIcon">{icon ?? <Inbox size={18} />}</span>
      <strong>{title}</strong>
      {description ? <p>{description}</p> : null}
      {action ? <div className="stateActions">{action}</div> : null}
    </div>
  );
}

/** Estado de erro padronizado, com ação opcional de retry. */
export function ErrorState({
  title = "Algo deu errado",
  description,
  onRetry,
  retrying = false
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  retrying?: boolean;
}) {
  return (
    <div className="stateBlock error" role="alert">
      <span className="stateIcon">
        <AlertCircle size={18} />
      </span>
      <strong>{title}</strong>
      {description ? <p>{description}</p> : null}
      {onRetry ? (
        <div className="stateActions">
          <LoadingButton
            className="toolbarButton compact"
            loading={retrying}
            icon={<RefreshCw size={14} />}
            onClick={onRetry}
          >
            Tentar novamente
          </LoadingButton>
        </div>
      ) : null}
    </div>
  );
}

/**
 * Alterna entre carregando / erro / vazio / conteúdo de forma consistente.
 * `loading` tem prioridade; depois `error`; depois `empty`; senão renderiza children.
 */
export function AsyncState({
  loading,
  error,
  empty,
  skeleton,
  emptyState,
  onRetry,
  retrying,
  children
}: {
  loading?: boolean;
  error?: string | null;
  empty?: boolean;
  skeleton?: ReactNode;
  emptyState?: ReactNode;
  onRetry?: () => void;
  retrying?: boolean;
  children: ReactNode;
}) {
  if (loading) return <>{skeleton ?? <SkeletonText lines={3} />}</>;
  if (error) return <ErrorState description={error} onRetry={onRetry} retrying={retrying} />;
  if (empty) return <>{emptyState ?? <EmptyState title="Nada por aqui ainda" />}</>;
  return <>{children}</>;
}

/**
 * Wrapper acessível para os modais (overlay + card).
 * Centraliza semântica de diálogo, fechamento por Esc, clique no overlay e
 * gestão de foco, para que todos os modais se comportem de forma consistente.
 */
export function Modal({
  onClose,
  labelledBy,
  className,
  children
}: {
  onClose: () => void;
  labelledBy: string;
  className?: string;
  children: ReactNode;
}) {
  const cardRef = useRef<HTMLDivElement>(null);

  // Foco entra no diálogo ao abrir e volta ao gatilho ao fechar (apenas no mount).
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    cardRef.current?.focus();
    return () => previouslyFocused?.focus?.();
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const card = cardRef.current;
      if (!card) return;
      const focusables = Array.from(
        card.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      ).filter((el) => el.offsetParent !== null);
      if (focusables.length === 0) {
        // Sem controles tabuláveis: mantém o foco no diálogo.
        e.preventDefault();
        card.focus();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || active === card)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modalOverlay" onClick={onClose}>
      <div
        ref={cardRef}
        className={className ? `modalCard ${className}` : "modalCard"}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

/** Alterna entre tema claro e escuro, persistindo a escolha em localStorage. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  // Sincroniza com o tema já aplicado pelo script inline (pós-hidratação).
  useEffect(() => {
    setTheme(document.documentElement.dataset.theme === "dark" ? "dark" : "light");
  }, []);

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    const root = document.documentElement;
    if (next === "dark") root.dataset.theme = "dark";
    else delete root.dataset.theme;
    try {
      window.localStorage.setItem("causor.theme", next);
    } catch {
      /* ignore */
    }
  }

  const isDark = theme === "dark";
  return (
    <button
      type="button"
      className="iconButton"
      onClick={toggle}
      aria-label={isDark ? "Mudar para tema claro" : "Mudar para tema escuro"}
      aria-pressed={isDark}
      title={isDark ? "Tema claro" : "Tema escuro"}
    >
      {isDark ? <Sun size={15} /> : <Moon size={15} />}
    </button>
  );
}

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
    <button
      type="button"
      className={active ? "navItem active" : "navItem"}
      title={label}
      aria-current={active ? "page" : undefined}
      onClick={onClick}
    >
      {icon}
      <span>{label}</span>
    </button>
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
