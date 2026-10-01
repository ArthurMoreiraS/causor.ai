"use client";

import { formatDate, sistemaBadge, statusLabel } from "@/lib/format";
import { previewText } from "@/lib/sanitize";
import type { IntimacaoRow } from "@/lib/views";
import type { Intimacao } from "@/lib/api";
import { DeadlineBadge, Empty, LoadingButton } from "../components/ui";

export default function IntimacoesView({
  rows,
  offline,
  onOpen,
  onCreateTask,
  onPrepareWork,
  onBackfill,
  onRetry,
  backfillProgress,
  backfillBusy
}: {
  rows: IntimacaoRow[];
  offline: boolean;
  onOpen: (intimacaoId: number) => void;
  onCreateTask?: (intimacao: Intimacao) => void;
  onPrepareWork: (intimacaoId: number, processoId: number | null, prazoId: number | null) => void;
  onBackfill?: () => void;
  onRetry?: (id: number) => void;
  backfillProgress?: string | null;
  backfillBusy?: boolean;
}) {
  return (
    <section className="dataTable inboxTable">
      {onBackfill ? <div className="inboxAnalysisBar">
        <div><strong>Análise de prazos</strong><p role="status">{backfillProgress || "Analise as intimações já recebidas e confira os prazos sugeridos."}</p></div>
        <LoadingButton type="button" loading={backfillBusy} disabled={offline} onClick={onBackfill}>
          {backfillBusy ? "Enfileirando análises…" : backfillProgress?.includes("Continuar") ? "Continuar análise" : "Analisar prazos já capturados"}
        </LoadingButton>
      </div> : null}
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
          <button type="button" className="deadlineOpen" aria-label={`Abrir prazo da intimação ${intimacao.id}`}
            onClick={e => { e.stopPropagation(); onOpen(intimacao.id); }}><DeadlineBadge prazo={prazo} analise={intimacao.prazo_analise} /></button>
          <span className={`queueStatus ${peticao?.status ?? "capturada"}`}>
            {peticao ? statusLabel(peticao.status) : "Sem minuta"}
          </span>
          <div className="dataRowEnd">
            <button
              className="toolbarButton compact primary"
              disabled={offline}
              onClick={(e) => {
                e.stopPropagation();
                onPrepareWork(intimacao.id, processo?.id ?? intimacao.processo_id ?? null, prazo?.id ?? null);
              }}
            >
              Preparar minuta
            </button>
            {onCreateTask ? <details className="secondaryActions" onClick={e => e.stopPropagation()}>
              <summary>Mais ações</summary>
              <button type="button" disabled={offline} onClick={() => onCreateTask(intimacao)}>Criar tarefa</button>
              {intimacao.prazo_analise?.status === "falha" ? <button type="button" disabled={offline} onClick={() => onRetry?.(intimacao.id)}>Tentar análise novamente</button> : null}
            </details> : null}
          </div>
        </article>
      ))}
      {!rows.length ? <Empty label="Nenhuma intimação encontrada" /> : null}
    </section>
  );
}
