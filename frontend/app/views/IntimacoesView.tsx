"use client";

import { useMemo, useState } from "react";
import { formatCnj, formatDate, sistemaBadge, statusLabel } from "@/lib/format";
import { previewText } from "@/lib/sanitize";
import type { IntimacaoRow } from "@/lib/views";
import type { Intimacao } from "@/lib/api";
import { DeadlineBadge, Empty, RowMenu } from "../components/ui";

type Aba = "abertas" | "sem_prazo" | "todas";

const ABAS: [Aba, string][] = [
  ["abertas", "Precisam de você"],
  ["sem_prazo", "Sem prazo"],
  ["todas", "Todas"]
];

/** Pauta, distribuição e expediente: a análise já concluiu que não há providência. */
function semPrazo(row: IntimacaoRow) {
  return !row.prazo && row.intimacao.prazo_analise?.status === "sem_prazo_identificado";
}

/** Ainda pede algo do escritório: prazo em aberto, triagem ou análise em curso. */
function emAberto(row: IntimacaoRow) {
  if (semPrazo(row) || row.prazo?.cumprido) return false;
  return !row.peticao || !["aprovada", "protocolada"].includes(row.peticao.status);
}

/** Prazos primeiro, do vencimento mais próximo; depois o resto na ordem recebida. */
function porVencimento(a: IntimacaoRow, b: IntimacaoRow) {
  if (a.prazo && b.prazo) return a.prazo.data_fatal.localeCompare(b.prazo.data_fatal);
  return a.prazo ? -1 : b.prazo ? 1 : 0;
}

export default function IntimacoesView({
  rows,
  offline,
  onOpen,
  onCreateTask,
  onPrepareWork,
  onRetry
}: {
  rows: IntimacaoRow[];
  offline: boolean;
  onOpen: (intimacaoId: number) => void;
  onCreateTask?: (intimacao: Intimacao) => void;
  onPrepareWork: (intimacaoId: number, processoId: number | null, prazoId: number | null) => void;
  onRetry?: (id: number) => void;
}) {
  const [aba, setAba] = useState<Aba>("abertas");
  const contagem = useMemo(() => ({
    abertas: rows.filter(emAberto).length,
    sem_prazo: rows.filter(semPrazo).length,
    todas: rows.length
  }), [rows]);
  const visiveis = useMemo(() => {
    if (aba === "todas") return rows;
    if (aba === "sem_prazo") return rows.filter(semPrazo);
    return rows.filter(emAberto).sort(porVencimento);
  }, [rows, aba]);

  return (
    <section className="dataTable inboxTable">
      <div className="inboxAnalysisBar">
        <div className="segmented" role="group" aria-label="Filtrar intimações">
          {ABAS.map(([key, label]) => (
            <button key={key} type="button" aria-pressed={aba === key} onClick={() => setAba(key)}>
              {label} ({contagem[key]})
            </button>
          ))}
        </div>
        <div className="inboxAnalysisText">
          <p>Prazos são calculados e avisados automaticamente a cada captura.</p>
        </div>
      </div>
      <div className="dataHead" aria-hidden="true">
        <span>Intimação</span>
        <span>Processo</span>
        <span>Sistema</span>
        <span>Prazo</span>
        <span>Minuta</span>
        <span className="dataRowEnd">Ação</span>
      </div>
      {visiveis.map((row) => {
        const { intimacao, processo, prazo, peticao } = row;
        const sistema = sistemaBadge(processo?.sistema);
        const numero = intimacao.numero_processo ?? processo?.numero;
        return (
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
              <span className="mono">{numero ? formatCnj(numero) : "Não identificado"}</span>
              <span>
                {intimacao.tribunal ?? processo?.tribunal ?? "-"} ·{" "}
                {formatDate(intimacao.data_publicacao ?? intimacao.data_disponibilizacao)}
              </span>
            </div>
            <span className={`pill ${sistema.className}`} title={sistema.title}>
              {sistema.label}
            </span>
            <button type="button" className="deadlineOpen" aria-label={`Abrir prazo da intimação ${intimacao.id}`}
              onClick={e => { e.stopPropagation(); onOpen(intimacao.id); }}><DeadlineBadge prazo={prazo} analise={intimacao.prazo_analise} />
              {intimacao.prazo_analise?.avisos?.length ? <span className="dayBadge neutral" title={intimacao.prazo_analise.avisos.join(" ")}>Conferir ato</span> : null}</button>
            <span className={`queueStatus ${peticao?.status ?? "capturada"}`}>
              {peticao ? statusLabel(peticao.status) : "Sem minuta"}
            </span>
            <div className="dataRowEnd">
              {semPrazo(row) ? null : (
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
              )}
              {onCreateTask ? <RowMenu>
                <button type="button" role="menuitem" disabled={offline} onClick={() => onCreateTask(intimacao)}>Criar tarefa</button>
                {intimacao.prazo_analise?.status === "falha" ? <button type="button" role="menuitem" disabled={offline} onClick={() => onRetry?.(intimacao.id)}>Tentar análise agora</button> : null}
              </RowMenu> : null}
            </div>
          </article>
        );
      })}
      {!visiveis.length ? <Empty label={aba === "abertas" ? "Nada pendente: nenhuma intimação precisa de você agora" : "Nenhuma intimação encontrada"} /> : null}
    </section>
  );
}
