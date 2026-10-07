"use client";

import { CalendarDays, CheckCircle2, Loader2 } from "lucide-react";
import type { Prazo } from "@/lib/api";
import { formatCnj, formatDate } from "@/lib/format";
import type { PrazoRow } from "@/lib/views";
import type { DetailSelection } from "../DetailDrawer";
import { DeadlineBadge, Empty, RowMenu } from "../components/ui";

function dueHint(prazo: Prazo, dias: number) {
  if (prazo.cumprido) return "cumprido";
  if (prazo.revisao_status !== "confirmado") return "a revisar";
  if (dias < 0) return "vencido";
  if (dias === 0) return "hoje";
  return dias === 1 ? "em 1 dia" : `em ${dias} dias`;
}

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
        <span>Prazo</span>
        <span>Processo</span>
        <span>Ato vinculado</span>
        <span>Situação</span>
        <span className="dataRowEnd">Ações</span>
      </div>
      {rows.map(({ prazo, processo, intimacao, peticao, dias }) => {
        const target: DetailSelection | null = processo
          ? { kind: "processo", id: processo.id }
          : intimacao
            ? { kind: "intimacao", id: intimacao.id }
            : null;
        const confirmed = prazo.revisao_status === "confirmado";
        const tone = prazo.cumprido ? "done" : !confirmed ? "" : dias <= 1 ? "risk" : dias <= 3 ? "warn" : "";
        const numero = processo?.numero ?? intimacao?.numero_processo;
        const review = !confirmed && intimacao;
        return (
          <article className="dataRow" key={prazo.id}>
            <div className={tone ? `filaDate ${tone}` : "filaDate"}>
              <strong>{formatDate(prazo.data_fatal)}</strong>
              <span>{dueHint(prazo, dias)}</span>
            </div>
            <div className="dataRowMain">
              <strong>{prazo.descricao ?? "Prazo"}</strong>
              <span>{prazo.dias} {prazo.dias_uteis ? "dias úteis" : "dias corridos"}</span>
            </div>
            <div className="dataRowMain">
              <span className="mono">{numero ? formatCnj(numero) : `Processo #${prazo.processo_id ?? "-"}`}</span>
              <span>{processo?.tribunal ?? intimacao?.tribunal ?? "Tribunal não informado"}</span>
            </div>
            <div className="dataRowMain">
              <strong>{intimacao?.tipo_comunicacao ?? peticao?.tipo ?? "Não informado"}</strong>
              <span>{intimacao ? formatDate(intimacao.data_publicacao ?? intimacao.data_disponibilizacao) : "—"}</span>
            </div>
            <DeadlineBadge prazo={prazo} />
            <div className="dataRowEnd">
              <button
                className={review ? "toolbarButton compact primary" : "toolbarButton compact"}
                disabled={busy === `edit-${prazo.id}` || offline}
                onClick={() => review ? onOpen({ kind: "intimacao", id: intimacao.id }) : onEditPrazo(prazo)}
              >
                {busy === `edit-${prazo.id}` ? <Loader2 className="spin" size={14} /> : <CalendarDays size={14} />}
                {review ? "Conferir" : "Revisar"}
              </button>
              <button
                className="toolbarButton compact"
                disabled={prazo.cumprido || !confirmed || busy === `done-${prazo.id}` || offline}
                title={!confirmed ? "Confirme o prazo antes de marcar como cumprido" : undefined}
                onClick={() => onDonePrazo(prazo)}
              >
                {busy === `done-${prazo.id}` ? <Loader2 className="spin" size={14} /> : <CheckCircle2 size={14} />}
                Cumprir
              </button>
              {target ? (
                <RowMenu>
                  <button type="button" role="menuitem" onClick={() => onOpen(target)}>
                    {target.kind === "processo" ? "Ver processo" : "Ver intimação"}
                  </button>
                </RowMenu>
              ) : null}
            </div>
          </article>
        );
      })}
      {!rows.length ? <Empty label="Nenhum prazo encontrado" /> : null}
    </section>
  );
}
