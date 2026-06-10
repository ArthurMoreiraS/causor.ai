"use client";

import {
  AlertTriangle,
  Bot,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock3,
  Download,
  FilePenLine,
  Gavel,
  HelpCircle,
  HomeIcon,
  Loader2,
  MessageCircle,
  RefreshCw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Table2,
  UserRound
} from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  aprovarPeticao,
  DashboardData,
  gerarMinuta,
  loadDashboard,
  Peticao,
  Prazo,
  protocolarPeticao
} from "@/lib/api";

const emptyData: DashboardData = {
  intimacoes: [],
  processos: [],
  prazos: [],
  peticoes: []
};

function formatDate(value: string | null | undefined) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(value));
}

function daysUntil(value: string) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(value);
  target.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - today.getTime()) / 86_400_000);
}

function statusLabel(status: Peticao["status"]) {
  if (status === "rascunho") return "Review";
  if (status === "aprovada") return "Approved";
  if (status === "protocolada") return "Filed";
  return status;
}

export default function Home() {
  const [data, setData] = useState<DashboardData>(emptyData);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setData(await loadDashboard());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load Causor data");
      setData(emptyData);
    } finally {
      setLoading(false);
    }
  }

  async function runAction(key: string, action: () => Promise<void>) {
    setBusy(key);
    setError(null);
    try {
      await action();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action could not be completed");
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const metrics = useMemo(() => {
    const openDeadlines = data.prazos.filter((p) => !p.cumprido);
    const urgent = openDeadlines.filter((p) => daysUntil(p.data_fatal) <= 3).length;
    return {
      monitored: data.processos.length,
      captured: data.intimacoes.length,
      pending: openDeadlines.length,
      overdue: urgent,
      drafts: data.peticoes.filter((p) => p.status === "rascunho").length
    };
  }, [data]);

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">
            <Gavel size={18} />
          </div>
          <strong>Causor</strong>
          <span>DEV</span>
        </div>

        <nav className="sideNav">
          <NavItem icon={<HomeIcon size={15} />} label="Home" />
          <NavGroup label="Agents">
            <NavItem icon={<Bot size={15} />} label="Deadline Operations" active />
            <NavItem icon={<FilePenLine size={15} />} label="Petition Drafting" />
            <NavItem icon={<ShieldCheck size={15} />} label="Filing Gate" />
            <NavItem icon={<CalendarDays size={15} />} label="Court Calendar" />
          </NavGroup>
          <NavGroup label="System of Record">
            <NavItem icon={<HomeIcon size={15} />} label="Cases" />
            <NavItem icon={<MessageCircle size={15} />} label="Intimations" />
            <NavItem icon={<Clock3 size={15} />} label="Deadlines" />
            <NavItem icon={<Table2 size={15} />} label="Audit Trail" />
          </NavGroup>
        </nav>

        <div className="sidebarFooter">
          <NavItem icon={<HelpCircle size={15} />} label="Help Center" />
          <NavItem icon={<Settings size={15} />} label="Settings" />
          <div className="profile">
            <div className="avatar">AM</div>
            <div>
              <strong>Arthur Moreira</strong>
              <span>causor.ai</span>
            </div>
            <ChevronDown size={14} />
          </div>
        </div>
      </aside>

      <section className="workspace">
        <header className="appbar">
          <div className="crumbs">
            <span>Legal Ops</span>
            <ChevronRight size={13} />
            <strong>Deadline Operations Agent</strong>
          </div>
          <div className="appActions">
            <button className="toolbarButton">
              <Settings size={15} />
              Settings
            </button>
            <button className="toolbarButton">
              <Clock3 size={15} />
              Activity
            </button>
            <button className="toolbarButton primary" onClick={refresh} disabled={loading}>
              {loading ? <Loader2 className="spin" size={15} /> : <RefreshCw size={15} />}
              Run Capture
            </button>
          </div>
        </header>

        <section className="hero">
          <h1>Deadline Operations Agent</h1>
        </section>

        {error ? (
          <div className="notice">
            <AlertTriangle size={18} />
            <span>{error}</span>
          </div>
        ) : null}

        <section className="metricStrip">
          <Metric label="Cases Monitored" value={metrics.monitored} />
          <Metric label="Intimations Captured" value={metrics.captured} />
          <Metric label="Pending Deadlines" value={metrics.pending} />
          <Metric label="High Risk" value={metrics.overdue} />
        </section>

        <section className="statusTabs">
          <button className="statusTab active">
            <Clock3 size={15} />
            Pending
          </button>
          <button className="statusTab">
            <Sparkles size={15} />
            Drafted
          </button>
          <button className="statusTab">
            <CheckCircle2 size={15} />
            Approved
          </button>
          <button className="statusTab">
            <Send size={15} />
            Filed
          </button>
        </section>

        <section className="workSurface">
          <div className="viewbar">
            <div className="segmented">
              <button className="selected">Collections</button>
              <button>Calendar</button>
              <button>Table</button>
            </div>
            <div className="viewActions">
              <label className="search">
                <Search size={15} />
                <input placeholder="Search case or client" />
              </label>
              <button className="toolbarButton compact">
                <SlidersHorizontal size={15} />
                Filters
              </button>
              <button className="toolbarButton compact">
                <Download size={15} />
                Export
              </button>
            </div>
          </div>

          <section className="amountCards">
            <AmountCard label="This Week" value={metrics.pending} detail="open deadlines" />
            <AmountCard label="Upcoming" value={metrics.drafts} detail="drafts awaiting review" />
            <AmountCard label="High Risk" value={metrics.overdue} detail="deadlines within 3 days" />
          </section>

          <section className="tablePanel">
            <div className="tableHeader">
              <span>Case</span>
              <span>Court</span>
              <span>Deadline</span>
              <span>Days</span>
              <span>Agent Action</span>
            </div>
            <div className="tableBody">
              {data.intimacoes.map((item) => {
                const prazo = data.prazos.find((p) => p.intimacao_id === item.id);
                return (
                  <article className="caseRow" key={item.id}>
                    <div className="caseCell">
                      <ChevronRight size={14} />
                      <div>
                        <strong>{item.numero_processo ?? "Unidentified case"}</strong>
                        <span>{item.tipo_comunicacao ?? "Court communication"}</span>
                      </div>
                    </div>
                    <span>{item.tribunal ?? "-"}</span>
                    <strong>{prazo ? formatDate(prazo.data_fatal) : formatDate(item.data_publicacao)}</strong>
                    <DeadlineBadge prazo={prazo} />
                    <button
                      className="iconButton"
                      title="Generate draft"
                      disabled={busy === `draft-${item.id}`}
                      onClick={() => runAction(`draft-${item.id}`, () => gerarMinuta(item.id))}
                    >
                      {busy === `draft-${item.id}` ? (
                        <Loader2 className="spin" size={15} />
                      ) : (
                        <Sparkles size={15} />
                      )}
                    </button>
                  </article>
                );
              })}
              {!data.intimacoes.length ? <Empty label="No captured intimations yet" /> : null}
            </div>
          </section>
        </section>

        <section className="bottomGrid">
          <Panel title="Approval Queue" action={`${data.peticoes.length} drafts`}>
            <div className="petitionList">
              {data.peticoes.map((peticao) => (
                <article className="petition" key={peticao.id}>
                  <div className="petitionHead">
                    <div>
                      <strong>{peticao.tipo ?? "Petition"}</strong>
                      <span>Case #{peticao.processo_id}</span>
                    </div>
                    <span className={`pill ${peticao.status}`}>{statusLabel(peticao.status)}</span>
                  </div>
                  <p>{peticao.conteudo ?? "No content"}</p>
                  <div className="petitionActions">
                    <button
                      className="toolbarButton"
                      disabled={peticao.status !== "rascunho" || busy === `approve-${peticao.id}`}
                      onClick={() =>
                        runAction(`approve-${peticao.id}`, () => aprovarPeticao(peticao.id))
                      }
                    >
                      <CheckCircle2 size={15} />
                      Approve
                    </button>
                    <button
                      className="toolbarButton primary"
                      disabled={peticao.status !== "aprovada" || busy === `file-${peticao.id}`}
                      onClick={() =>
                        runAction(`file-${peticao.id}`, () => protocolarPeticao(peticao.id))
                      }
                    >
                      <Send size={15} />
                      File
                    </button>
                  </div>
                </article>
              ))}
              {!data.peticoes.length ? <Empty label="No petitions awaiting approval" /> : null}
            </div>
          </Panel>

          <Panel title="Human Gate" action="active">
            <div className="gate">
              <ShieldCheck size={26} />
              <div>
                <strong>Approval required before filing</strong>
                <span>Draft petitions cannot be filed until a responsible lawyer approves them.</span>
              </div>
            </div>
          </Panel>
        </section>
      </section>
    </main>
  );
}

function NavGroup({ label, children }: { label: string; children: ReactNode }) {
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

function NavItem({
  icon,
  label,
  active = false
}: {
  icon: ReactNode;
  label: string;
  active?: boolean;
}) {
  return (
    <a className={active ? "active" : ""} href="#">
      {icon}
      <span>{label}</span>
    </a>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AmountCard({ label, value, detail }: { label: string; value: number; detail: string }) {
  return (
    <article className="amountCard">
      <span>{label}</span>
      <strong>{value.toLocaleString("en-US")}</strong>
      <small>{detail}</small>
    </article>
  );
}

function Panel({
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

function DeadlineBadge({ prazo }: { prazo: Prazo | undefined }) {
  if (!prazo) return <span className="dayBadge neutral">Pending</span>;
  const remaining = daysUntil(prazo.data_fatal);
  if (prazo.cumprido) return <span className="dayBadge done">Done</span>;
  if (remaining <= 0) return <span className="dayBadge risk">Due</span>;
  if (remaining <= 3) return <span className="dayBadge today">{remaining}d</span>;
  return <span className="dayBadge neutral">{remaining}d</span>;
}

function Empty({ label }: { label: string }) {
  return (
    <div className="empty">
      <UserRound size={18} />
      <span>{label}</span>
    </div>
  );
}
