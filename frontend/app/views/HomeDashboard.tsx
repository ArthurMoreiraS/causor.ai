"use client";

import { Bot, CheckCircle2, Clock3, FilePenLine, Inbox, MessageCircle, Scale, Search, Send, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import type { ConnectorStatus } from "@/lib/api";
import { connectorStatusLabel, formatDate } from "@/lib/format";
import type { PrazoRow, ViewKey } from "@/lib/views";
import { CommandStat, DeadlineBadge, Empty, FeatureTile, LoadingButton, Panel } from "../components/ui";

export default function HomeDashboard({
  metrics,
  prazoRows,
  operationalConnectors,
  offline,
  busy,
  worklistSlot,
  onOpenOab,
  onOpenAssistant,
  onNavigate
}: {
  metrics: {
    monitored: number;
    captured: number;
    pending: number;
    highRisk: number;
    drafts: number;
    approved: number;
    overdue: number;
    withoutDraft: number;
    compliance: number;
  };
  prazoRows: PrazoRow[];
  operationalConnectors: ConnectorStatus[];
  offline: boolean;
  busy: string | null;
  worklistSlot?: ReactNode;
  onOpenOab: () => void;
  onOpenAssistant: () => void;
  onNavigate: (view: ViewKey) => void;
}) {
  const nextDeadline = prazoRows.find((row) => !row.prazo.cumprido) ?? null;
  const agentCycle = [
    {
      label: "Captura",
      detail: `${metrics.captured} ${metrics.captured === 1 ? "intimação" : "intimações"}`,
      status: metrics.captured > 0 ? "complete" : "active",
      icon: <Search size={15} />
    },
    {
      label: "Prazo",
      detail: `${metrics.pending} pendente${metrics.pending === 1 ? "" : "s"}`,
      status: metrics.pending > 0 ? "active" : metrics.captured > 0 ? "complete" : "queued",
      icon: <Clock3 size={15} />
    },
    {
      label: "Minuta",
      detail: `${metrics.drafts} em revisão`,
      status: metrics.drafts > 0 ? "review" : "queued",
      icon: <FilePenLine size={15} />
    },
    {
      label: "Gate OAB",
      detail: `${metrics.approved} liberada${metrics.approved === 1 ? "" : "s"}`,
      status: metrics.approved > 0 ? "active" : metrics.drafts > 0 ? "review" : "queued",
      icon: <ShieldCheck size={15} />
    },
    {
      label: "PJe assistido",
      detail: metrics.approved > 0 ? "aguardando ready_to_sign" : "sem peça liberada",
      status: metrics.approved > 0 ? "waiting" : "queued",
      icon: <Send size={15} />
    },
    {
      label: "Auditoria",
      detail: "log completo do ato",
      status: "queued",
      icon: <CheckCircle2 size={15} />
    }
  ];

  return (
    <section className="homeSurface">
      <section className="homeCommand">
        <div className="commandPanel primaryCommand">
          <div>
            <span className="sectionKicker">Hoje</span>
            <h2>Prioridade operacional</h2>
            <strong>
              {metrics.highRisk > 0
                ? `${metrics.highRisk} prazo${metrics.highRisk > 1 ? "s" : ""} em alto risco`
                : "Nenhum alto risco aberto"}
            </strong>
            <p>
              {nextDeadline
                ? `${nextDeadline.prazo.descricao ?? "Prazo"} vence em ${formatDate(
                    nextDeadline.prazo.data_fatal
                  )}.`
                : "A fila está sem vencimentos pendentes no momento."}
            </p>
          </div>
          <div className="quickActions">
            <LoadingButton
              className="toolbarButton primary"
              icon={<Search size={15} />}
              loading={busy === "capture"}
              onClick={onOpenOab}
              disabled={busy === "capture" || offline}
            >
              {busy === "capture" ? "Capturando..." : "Captura por OAB"}
            </LoadingButton>
            <button className="toolbarButton" onClick={onOpenAssistant} disabled={offline}>
              <MessageCircle size={15} />
              Assistente
            </button>
          </div>
        </div>

        <div className="commandStats">
          <CommandStat label="Processos" value={metrics.monitored} detail="monitorados" />
          <CommandStat label="Intimações" value={metrics.captured} detail="capturadas" />
          <CommandStat label="Prazos" value={metrics.pending} detail="pendentes" />
          <CommandStat
            label="Prazos em dia"
            value={`${metrics.compliance}%`}
            detail={`${metrics.overdue} vencido(s)`}
            tone={metrics.overdue > 0 ? "risk" : metrics.highRisk > 0 ? "warn" : "ok"}
          />
        </div>
      </section>

      <section className="agentCyclePanel" aria-label="Ciclo operacional do agente">
        <header>
          <div>
            <span className="sectionKicker">Ciclo do agente</span>
            <strong>Da captura ao protocolo assistido</strong>
          </div>
          <span className={`cycleHealth ${metrics.highRisk > 0 ? "risk" : "ok"}`}>
            <Bot size={14} />
            {metrics.highRisk > 0 ? "atenção em prazos" : "operação estável"}
          </span>
        </header>
        <div className="agentCycle">
          {agentCycle.map((step, index) => (
            <button
              className={`agentCycleStep ${step.status}`}
              key={step.label}
              title={`${step.label} — ${step.detail}`}
              onClick={() =>
                onNavigate(
                  step.label === "Captura"
                    ? "intimacoes"
                    : step.label === "Prazo"
                      ? "prazos"
                      : step.label === "Minuta"
                        ? "peticoes"
                        : step.label === "Gate OAB" || step.label === "PJe assistido"
                          ? "gate"
                          : "auditoria"
                )
              }
            >
              <span className="cycleIndex">{String(index + 1).padStart(2, "0")}</span>
              <span className="cycleIcon">{step.icon}</span>
              <span className="cycleCopy">
                <strong>{step.label}</strong>
                <small>{step.detail}</small>
              </span>
            </button>
          ))}
        </div>
      </section>

      {worklistSlot ? <section className="dashboardWorklist">{worklistSlot}</section> : null}

      <section className="homeGrid">
        <Panel title="Agenda de prazos" action="próximos vencimentos">
          <div className="deadlineAgenda">
            {prazoRows.map(({ prazo, processo, dias }) => (
              <button className="deadlineAgendaItem" key={prazo.id} onClick={() => onNavigate("prazos")}>
                <div className="dateBlock">
                  <strong>{formatDate(prazo.data_fatal).slice(0, 5)}</strong>
                  <span>{dias < 0 ? "vencido" : `${dias}d`}</span>
                </div>
                <div>
                  <strong>{prazo.descricao ?? "Prazo"}</strong>
                  <span className="mono">{processo?.numero ?? `Processo #${prazo.processo_id ?? "-"}`}</span>
                </div>
                <DeadlineBadge prazo={prazo} />
              </button>
            ))}
            {!prazoRows.length ? <Empty label="Nenhum prazo registrado" /> : null}
          </div>
        </Panel>

        <Panel title="Saúde operacional" action={offline ? "offline" : "online"}>
          <div className="connectorGrid compactConnectors">
            {operationalConnectors.map((connector) => (
              <article className={`connector ${connector.status}`} key={connector.name}>
                <div>
                  <strong>{connector.name}</strong>
                  <span>{connector.detail}</span>
                </div>
                <small>{connectorStatusLabel(connector.status)}</small>
              </article>
            ))}
          </div>
        </Panel>
      </section>

      <Panel title="Áreas de trabalho" action="atalhos">
          <div className="featureTiles">
            <FeatureTile icon={<Scale size={16} />} label="Processos" value={metrics.monitored} onClick={() => onNavigate("processos")} />
            <FeatureTile icon={<Inbox size={16} />} label="Intimações" value={metrics.captured} onClick={() => onNavigate("intimacoes")} />
            <FeatureTile icon={<Clock3 size={16} />} label="Prazos" value={metrics.pending} onClick={() => onNavigate("prazos")} />
            <FeatureTile icon={<FilePenLine size={16} />} label="Minutas" value={metrics.drafts + metrics.approved} onClick={() => onNavigate("peticoes")} />
            <FeatureTile icon={<ShieldCheck size={16} />} label="Gate OAB" value={metrics.approved} onClick={() => onNavigate("gate")} />
          </div>
      </Panel>
    </section>
  );
}
