"use client";

import { CalendarDays, CheckCircle2, ChevronRight, Loader2 } from "lucide-react";
import type { Prazo } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { PrazoRow } from "@/lib/views";
import type { DetailSelection } from "../DetailDrawer";
import { DeadlineBadge, Empty } from "../components/ui";

export default function PrazosView({
  rows,
  busy,
  offline,
  onOpen,
  onDonePrazo,
  onEditPrazo
}: {
  rows: PrazoRow[];
  busy: string | null;
  offline: boolean;
  onOpen: (sel: DetailSelection) => void;
  onDonePrazo: (prazo: Prazo) => void;
  onEditPrazo: (prazo: Prazo) => void;
}) {
  return (
    <section className="dataTable deadlineTable">
      <div className="dataHead" aria-hidden="true">
        <span>Data fatal</span>
        <span>Prazo / processo</span>
        <span>Ato vinculado</span>
        <span>Status</span>
        <span className="dataRowEnd">Ações</span>
      </div>
      {rows.map(({ prazo, processo, intimacao, peticao, dias }) => {
        const target: DetailSelection | null = processo
          ? { kind: "processo", id: processo.id }
          : intimacao
            ? { kind: "intimacao", id: intimacao.id }
            : null;
        const tone = prazo.cumprido ? "done" : dias <= 1 ? "risk" : dias <= 3 ? "warn" : "";
        return (
          <article className="dataRow" key={prazo.id}>
            <div className={tone ? `filaDate ${tone}` : "filaDate"}>
              <strong>{formatDate(prazo.data_fatal).slice(0, 5)}</strong>
              <span>{dias < 0 ? "vencido" : `${dias}d`}</span>
            </div>
            <div className="dataRowMain">
              <strong>{prazo.descricao ?? "Prazo"}</strong>
              <span className="mono">
                {processo?.numero ?? `Processo #${prazo.processo_id ?? "-"}`}
              </span>
            </div>
            <span className="cellText">
              {intimacao?.tipo_comunicacao ?? peticao?.tipo ?? "Não informado"}
            </span>
            <DeadlineBadge prazo={prazo} />
            <div className="dataRowEnd">
              {target ? (
                <button className="toolbarButton compact" onClick={() => onOpen(target)}>
                  <ChevronRight size={15} />
                  Detalhes
                </button>
              ) : null}
              <button
                className="toolbarButton compact"
                disabled={prazo.cumprido || busy === `done-${prazo.id}` || offline}
                onClick={() => onDonePrazo(prazo)}
              >
                {busy === `done-${prazo.id}` ? (
                  <Loader2 className="spin" size={15} />
                ) : (
                  <CheckCircle2 size={15} />
                )}
                Cumprir
              </button>
              <button
                className="toolbarButton compact"
                disabled={busy === `edit-${prazo.id}` || offline}
                onClick={() => void onEditPrazo(prazo)}
              >
                {busy === `edit-${prazo.id}` ? (
                  <Loader2 className="spin" size={15} />
                ) : (
                  <CalendarDays size={15} />
                )}
                Revisar
              </button>
            </div>
          </article>
        );
      })}
      {!rows.length ? <Empty label="Nenhum prazo encontrado" /> : null}
    </section>
  );
}
