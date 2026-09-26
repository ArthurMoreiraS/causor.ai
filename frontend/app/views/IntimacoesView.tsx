"use client";

import { formatDate, sistemaBadge, statusLabel } from "@/lib/format";
import { previewText } from "@/lib/sanitize";
import type { IntimacaoRow } from "@/lib/views";
import type { Intimacao } from "@/lib/api";
import { DeadlineBadge, Empty } from "../components/ui";

export default function IntimacoesView({
  rows,
  offline,
  onOpen,
  onCreateTask,
  onPrepareWork
}: {
  rows: IntimacaoRow[];
  offline: boolean;
  onOpen: (intimacaoId: number) => void;
  onCreateTask?: (intimacao: Intimacao) => void;
  onPrepareWork: (intimacaoId: number, processoId: number | null, prazoId: number | null) => void;
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
              disabled={offline}
              onClick={(e) => {
                e.stopPropagation();
                onPrepareWork(intimacao.id, processo?.id ?? intimacao.processo_id ?? null, prazo?.id ?? null);
              }}
            >
              Preparar trabalho
            </button>
          </div>
        </article>
      ))}
      {!rows.length ? <Empty label="Nenhuma intimação encontrada" /> : null}
    </section>
  );
}
