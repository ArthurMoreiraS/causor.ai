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
    <section className="deadlineBoard">
      {rows.map(({ prazo, processo, intimacao, peticao, dias }) => {
        const target: DetailSelection | null = processo
          ? { kind: "processo", id: processo.id }
          : intimacao
            ? { kind: "intimacao", id: intimacao.id }
            : null;
        return (
        <article className="deadlineCard" key={prazo.id}>
          <div className="dateBlock large">
            <strong>{formatDate(prazo.data_fatal).slice(0, 5)}</strong>
            <span>{dias < 0 ? "vencido" : `${dias}d`}</span>
          </div>
          <div className="deadlineMain">
            <header>
              <div>
                <strong>{prazo.descricao ?? "Prazo"}</strong>
                <span>{processo?.numero ?? `Processo #${prazo.processo_id ?? "-"}`}</span>
              </div>
              <DeadlineBadge prazo={prazo} />
            </header>
            <p>{intimacao?.tipo_comunicacao ?? peticao?.tipo ?? "Ato vinculado não informado"}</p>
            <div className="rowActions">
              {target ? (
                <button className="toolbarButton" onClick={() => onOpen(target)}>
                  <ChevronRight size={15} />
                  Detalhes
                </button>
              ) : null}
              <button
                className="toolbarButton"
                disabled={prazo.cumprido || busy === `done-${prazo.id}` || offline}
                onClick={() => onDonePrazo(prazo)}
              >
                {busy === `done-${prazo.id}` ? <Loader2 className="spin" size={15} /> : <CheckCircle2 size={15} />}
                Cumprir
              </button>
              <button
                className="toolbarButton"
                disabled={busy === `edit-${prazo.id}` || offline}
                onClick={() => void onEditPrazo(prazo)}
              >
                {busy === `edit-${prazo.id}` ? <Loader2 className="spin" size={15} /> : <CalendarDays size={15} />}
                Revisar
              </button>
            </div>
          </div>
        </article>
        );
      })}
      {!rows.length ? <Empty label="Nenhum prazo encontrado" /> : null}
    </section>
  );
}
