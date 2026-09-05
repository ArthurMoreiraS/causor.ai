"use client";

import { CheckCircle2, Send, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import type { Peticao } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { PeticaoRow } from "@/lib/views";
import { CommandStat, Empty } from "../components/ui";

export default function GateOabView({
  rows,
  busy,
  offline,
  onApprove,
  onFile
}: {
  rows: PeticaoRow[];
  busy: string | null;
  offline: boolean;
  onApprove: (peticao: Peticao) => void;
  onFile: (peticao: Peticao) => void;
}) {
  const awaiting = rows.filter((row) => ["rascunho", "em_revisao"].includes(row.peticao.status));
  const cleared = rows.filter((row) => row.peticao.status === "aprovada");
  const filed = rows.filter((row) => row.peticao.status === "protocolada");

  return (
    <section className="gateView">
      <div className="gateSummary">
        <CommandStat label="Aguardando revisão" value={awaiting.length} detail="revisão humana" />
        <CommandStat label="Liberadas" value={cleared.length} detail="prontas para protocolo" />
        <CommandStat label="Protocoladas" value={filed.length} detail="ato finalizado" />
      </div>

      <section className="gateLanes">
        <GateLane
          title="Revisão do advogado"
          rows={awaiting}
          busy={busy}
          offline={offline}
          primaryLabel="Aprovar"
          primaryIcon={<CheckCircle2 size={15} />}
          onPrimary={onApprove}
        />
        <GateLane
          title="Liberadas para protocolo"
          rows={cleared}
          busy={busy}
          offline={offline}
          primaryLabel="Preparar protocolo"
          primaryIcon={<Send size={15} />}
          onPrimary={onFile}
          primary
        />
        <GateLane
          title="Protocoladas"
          rows={filed}
          busy={busy}
          offline={offline}
          primaryLabel="Protocolada"
          primaryIcon={<ShieldCheck size={15} />}
          onPrimary={() => undefined}
          readonly
        />
      </section>
    </section>
  );
}

function GateLane({
  title,
  rows,
  busy,
  offline,
  primaryLabel,
  primaryIcon,
  onPrimary,
  primary = false,
  readonly = false
}: {
  title: string;
  rows: PeticaoRow[];
  busy: string | null;
  offline: boolean;
  primaryLabel: string;
  primaryIcon: ReactNode;
  onPrimary: (peticao: Peticao) => void;
  primary?: boolean;
  readonly?: boolean;
}) {
  return (
    <section className="gateLane">
      <header>
        <strong>{title}</strong>
        <span>{rows.length}</span>
      </header>
      <div className="gateLaneBody">
        {rows.map(({ peticao, processo, prazo }) => (
          <article className="gateCard" key={peticao.id}>
            <div>
              <strong>{peticao.tipo ?? "Petição"}</strong>
              <span className="mono">{processo?.numero ?? `Processo #${peticao.processo_id}`}</span>
            </div>
            <p>{peticao.conteudo ?? "Sem conteúdo"}</p>
            <small>{prazo ? `Vence em ${formatDate(prazo.data_fatal)}` : "Sem prazo vinculado"}</small>
            <button
              className={primary ? "toolbarButton primary" : "toolbarButton"}
              disabled={readonly || offline || busy === `approve-${peticao.id}` || busy === `file-${peticao.id}`}
              onClick={() => onPrimary(peticao)}
            >
              {primaryIcon}
              {primaryLabel}
            </button>
          </article>
        ))}
        {!rows.length ? <Empty label="Sem itens" /> : null}
      </div>
    </section>
  );
}
