"use client";

import { Clock3, FilePenLine, HomeIcon, MessageCircle, Search, ShieldCheck } from "lucide-react";
import type { ConnectorStatus, ReviewQueueItem } from "@/lib/api";
import { connectorStatusLabel, formatDate, reviewStatusLabel, riskLabel } from "@/lib/format";
import type { PrazoRow, ViewKey } from "@/lib/views";
import { CommandStat, DeadlineBadge, Empty, FeatureTile, Panel } from "../components/ui";

export default function HomeDashboard({
  metrics,
  priorityQueue,
  prazoRows,
  operationalConnectors,
  offline,
  busy,
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
  priorityQueue: ReviewQueueItem[];
  prazoRows: PrazoRow[];
  operationalConnectors: ConnectorStatus[];
  offline: boolean;
  busy: string | null;
  onOpenOab: () => void;
  onOpenAssistant: () => void;
  onNavigate: (view: ViewKey) => void;
}) {
  const nextDeadline = prazoRows.find((row) => !row.prazo.cumprido) ?? null;

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
            <button className="toolbarButton primary" onClick={onOpenOab} disabled={busy === "capture" || offline}>
              <Search size={15} />
              Captura por OAB
            </button>
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
          <CommandStat label="Prazos em dia" value={`${metrics.compliance}%`} detail={`${metrics.overdue} vencido(s)`} />
        </div>
      </section>

      <section className="homeGrid">
        <Panel title="Prioridades agora" action={`${priorityQueue.length} itens`}>
          <div className="priorityList">
            {priorityQueue.map((item) => (
              <button
                className="priorityItem"
                key={item.intimacao.id}
                onClick={() => onNavigate(item.prazo ? "prazos" : "intimacoes")}
              >
                <div>
                  <strong>{item.intimacao.numero_processo ?? "Processo não identificado"}</strong>
                  <span>{item.intimacao.tipo_comunicacao ?? "Comunicação judicial"}</span>
                </div>
                <div className="priorityMeta">
                  <small className={`riskText ${item.risco}`}>{riskLabel(item.risco)}</small>
                  <span>{reviewStatusLabel(item.status)}</span>
                </div>
              </button>
            ))}
            {!priorityQueue.length ? <Empty label="Nenhuma prioridade aberta" /> : null}
          </div>
        </Panel>

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
                  <span>{processo?.numero ?? `Processo #${prazo.processo_id ?? "-"}`}</span>
                </div>
                <DeadlineBadge prazo={prazo} />
              </button>
            ))}
            {!prazoRows.length ? <Empty label="Nenhum prazo registrado" /> : null}
          </div>
        </Panel>
      </section>

      <section className="homeGrid">
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

        <Panel title="Áreas de trabalho" action="atalhos">
          <div className="featureTiles">
            <FeatureTile icon={<HomeIcon size={16} />} label="Processos" value={metrics.monitored} onClick={() => onNavigate("processos")} />
            <FeatureTile icon={<MessageCircle size={16} />} label="Intimações" value={metrics.captured} onClick={() => onNavigate("intimacoes")} />
            <FeatureTile icon={<Clock3 size={16} />} label="Prazos" value={metrics.pending} onClick={() => onNavigate("prazos")} />
            <FeatureTile icon={<FilePenLine size={16} />} label="Minutas" value={metrics.drafts + metrics.approved} onClick={() => onNavigate("peticoes")} />
            <FeatureTile icon={<ShieldCheck size={16} />} label="Gate OAB" value={metrics.approved} onClick={() => onNavigate("gate")} />
          </div>
        </Panel>
      </section>
    </section>
  );
}
