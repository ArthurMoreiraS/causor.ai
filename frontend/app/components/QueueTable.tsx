"use client";

import { CalendarDays, CheckCircle2, ChevronRight, Loader2, Sparkles } from "lucide-react";
import type { Prazo, ReviewQueueItem } from "@/lib/api";
import { formatDate, reviewStatusLabel } from "@/lib/format";
import { DeadlineBadge, Empty } from "./ui";

export default function QueueTable({
  items,
  busy,
  offline,
  emptyLabel,
  onGenerateDraft,
  onDonePrazo,
  onEditPrazo
}: {
  items: ReviewQueueItem[];
  busy: string | null;
  offline: boolean;
  emptyLabel: string;
  onGenerateDraft: (intimacaoId: number) => void;
  onDonePrazo: (prazo: Prazo) => void;
  onEditPrazo: (prazo: Prazo) => void;
}) {
  return (
    <section className="tablePanel">
      <div className="tableHeader">
        <span>Processo</span>
        <span>Sistema</span>
        <span>Vencimento</span>
        <span>Risco</span>
        <span>Status</span>
        <span>Ações</span>
      </div>
      <div className="tableBody">
        {items.map((item) => {
          const { intimacao, prazo, processo } = item;
          return (
            <article className="caseRow" key={intimacao.id}>
              <div className="caseCell">
                <ChevronRight size={14} />
                <div>
                  <strong className="mono">{intimacao.numero_processo ?? "Processo não identificado"}</strong>
                  <span>{intimacao.tipo_comunicacao ?? "Comunicação judicial"}</span>
                  <small>{intimacao.teor ?? "Teor não informado"}</small>
                </div>
              </div>
              <span>{processo?.sistema ?? intimacao.tribunal ?? "-"}</span>
              <strong>
                {prazo ? formatDate(prazo.data_fatal) : formatDate(intimacao.data_publicacao)}
              </strong>
              <DeadlineBadge prazo={prazo} />
              <span className={`queueStatus ${item.status}`}>
                {reviewStatusLabel(item.status)}
              </span>
              <div className="rowActions">
                <button
                  className="iconButton"
                  title="Gerar minuta"
                  disabled={busy === `draft-${intimacao.id}` || offline}
                  onClick={() => onGenerateDraft(intimacao.id)}
                >
                  {busy === `draft-${intimacao.id}` ? (
                    <Loader2 className="spin" size={15} />
                  ) : (
                    <Sparkles size={15} />
                  )}
                </button>
                <button
                  className="iconButton"
                  title="Marcar prazo cumprido"
                  disabled={!prazo || prazo.cumprido || busy === `done-${prazo?.id}` || offline}
                  onClick={() => (prazo ? onDonePrazo(prazo) : undefined)}
                >
                  {busy === `done-${prazo?.id}` ? (
                    <Loader2 className="spin" size={15} />
                  ) : (
                    <CheckCircle2 size={15} />
                  )}
                </button>
                <button
                  className="iconButton"
                  title="Editar data fatal"
                  disabled={!prazo || busy === `edit-${prazo?.id}` || offline}
                  onClick={() => (prazo ? void onEditPrazo(prazo) : undefined)}
                >
                  {busy === `edit-${prazo?.id}` ? (
                    <Loader2 className="spin" size={15} />
                  ) : (
                    <CalendarDays size={15} />
                  )}
                </button>
              </div>
            </article>
          );
        })}
        {!items.length ? <Empty label={emptyLabel} /> : null}
      </div>
    </section>
  );
}
