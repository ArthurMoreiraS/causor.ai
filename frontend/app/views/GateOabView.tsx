"use client";

import { CheckCircle2, FilePenLine } from "lucide-react";
import type { ReactNode } from "react";
import type { Peticao } from "@/lib/api";
import { formatCnj, formatDate } from "@/lib/format";
import type { PeticaoRow } from "@/lib/views";
import { CommandStat, Empty } from "../components/ui";

export default function GateOabView({
  rows,
  busy,
  offline,
  onApprove,
  onOpenEditor
}: {
  rows: PeticaoRow[];
  busy: string | null;
  offline: boolean;
  /** Ausente para quem não aprova (assistente): a fila só abre a minuta. */
  onApprove?: (peticao: Peticao) => void;
  onOpenEditor: (peticao: Peticao) => void;
}) {
  const awaiting = rows.filter((row) => ["rascunho", "em_revisao"].includes(row.peticao.status));
  const cleared = rows.filter((row) => row.peticao.status === "aprovada");

  return (
    <section className="gateView">
      <div className="gateSummary">
        <CommandStat label="Aguardando revisão" value={awaiting.length} detail="revisão humana" />
        <CommandStat label="Revisadas" value={cleared.length} detail="aprovadas pelo advogado" />
      </div>

      <section className="gateLanes">
        <GateLane
          title="Revisão do advogado"
          rows={awaiting}
          busy={busy}
          offline={offline}
          primaryLabel={onApprove ? "Aprovar" : "Abrir minuta"}
          primaryIcon={onApprove ? <CheckCircle2 size={15} /> : <FilePenLine size={15} />}
          onPrimary={onApprove ?? onOpenEditor}
        />
        <GateLane
          title="Minutas aprovadas"
          rows={cleared}
          busy={busy}
          offline={offline}
          primaryLabel="Ver minuta"
          primaryIcon={<FilePenLine size={15} />}
          onPrimary={onOpenEditor}
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
}: {
  title: string;
  rows: PeticaoRow[];
  busy: string | null;
  offline: boolean;
  primaryLabel: string;
  primaryIcon: ReactNode;
  onPrimary: (peticao: Peticao) => void;
  primary?: boolean;
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
              <span className="mono">{processo?.numero ? formatCnj(processo.numero) : `Processo #${peticao.processo_id}`}</span>
            </div>
            <p>{peticao.conteudo ?? "Sem conteúdo"}</p>
            <small>{prazo ? `Vence em ${formatDate(prazo.data_fatal)}` : "Sem prazo vinculado"}</small>
            <button
              className={primary ? "toolbarButton primary" : "toolbarButton"}
              disabled={offline || busy === `approve-${peticao.id}`}
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
