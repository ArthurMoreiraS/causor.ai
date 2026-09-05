"use client";

import { Loader2, Sparkles } from "lucide-react";
import { formatDate, sistemaBadge, statusLabel } from "@/lib/format";
import { previewText } from "@/lib/sanitize";
import type { IntimacaoRow } from "@/lib/views";
import type { Intimacao } from "@/lib/api";
import { DeadlineBadge, Empty } from "../components/ui";

export default function IntimacoesView({
  rows,
  busy,
  offline,
  onOpen,
  onCreateTask,
  onGenerateDraft
}: {
  rows: IntimacaoRow[];
  busy: string | null;
  offline: boolean;
  onOpen: (intimacaoId: number) => void;
  onCreateTask?: (intimacao: Intimacao) => void;
  onGenerateDraft: (intimacaoId: number) => void;
}) {
  return (
    <section className="dataTable inboxTable">
      <div className="dataHead" aria-hidden="true">
        <span>Intimação</span>
        <span>Processo</span>
        <span>Sistema</span>
        <span>Prazo</span>
        <span>Minuta</span>
        <span className="dataRowEnd">Ação</span>
      </div>
      {rows.map(({ intimacao, processo, prazo, peticao }) => (
        <article
          className="dataRow clickable"
          key={intimacao.id}
          onClick={() => onOpen(intimacao.id)}
        >
          <div className="dataRowMain">
            <strong>{intimacao.tipo_comunicacao ?? "Comunicação judicial"}</strong>
            <span>{previewText(intimacao.teor ?? "") || "Teor não informado"}</span>
          </div>
          <div className="dataRowMain">
            <strong className="mono">
              {intimacao.numero_processo ?? processo?.numero ?? "Não identificado"}
            </strong>
            <span>
              {intimacao.tribunal ?? processo?.tribunal ?? "-"} ·{" "}
              {formatDate(intimacao.data_publicacao ?? intimacao.data_disponibilizacao)}
            </span>
          </div>
          <span
            className={`pill ${sistemaBadge(processo?.sistema).className}`}
            title={sistemaBadge(processo?.sistema).title}
          >
            {sistemaBadge(processo?.sistema).label}
          </span>
          <DeadlineBadge prazo={prazo} />
          <span className={`queueStatus ${peticao?.status ?? "capturada"}`}>
            {peticao ? statusLabel(peticao.status) : "Sem minuta"}
          </span>
          <div className="dataRowEnd">
            {onCreateTask ? <button type="button" className="toolbarButton compact" disabled={offline}
              onClick={e => { e.stopPropagation(); onCreateTask(intimacao); }}>Criar tarefa</button> : null}
            <button
              className="toolbarButton compact"
              disabled={busy === `draft-${intimacao.id}` || offline}
              onClick={(e) => {
                e.stopPropagation();
                onGenerateDraft(intimacao.id);
              }}
            >
              {busy === `draft-${intimacao.id}` ? (
                <Loader2 className="spin" size={15} />
              ) : (
                <Sparkles size={15} />
              )}
              Minutar
            </button>
          </div>
        </article>
      ))}
      {!rows.length ? <Empty label="Nenhuma intimação encontrada" /> : null}
    </section>
  );
}
