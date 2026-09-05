"use client";

import { CheckCircle2, FilePenLine, Loader2, Send, Sparkles, Table2 } from "lucide-react";
import { useMemo, useState } from "react";
import type { Peticao, ReviewQueueItem } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { ViewKey } from "@/lib/views";
import { Empty, Pagination } from "../components/ui";

const PAGE_SIZE = 8;

function prioridade(item: ReviewQueueItem): number {
  if (item.status === "protocolada" || item.status === "cumprido") return 9;
  const dias = item.dias_para_vencer;
  if (dias === null) return 5;
  if (dias < 0) return 0;
  if (dias === 0) return 1;
  if (dias === 1) return 2;
  if (dias <= 3) return 3;
  return 4;
}

/** Tom de urgência da linha: dirige a borda esquerda e o bloco de data. */
function tomDeRisco(item: ReviewQueueItem): "risk" | "warn" | "done" | "" {
  if (item.status === "protocolada" || item.status === "cumprido") return "done";
  const dias = item.dias_para_vencer;
  if (dias === null) return "";
  if (dias <= 1) return "risk";
  if (dias <= 3) return "warn";
  return "";
}

function badgeDePrazo(item: ReviewQueueItem) {
  const dias = item.dias_para_vencer;
  if (item.status === "protocolada") {
    return <span className="dayBadge done">Protocolo registrado</span>;
  }
  if (item.status === "cumprido") {
    return <span className="dayBadge done">Prazo cumprido</span>;
  }
  if (dias === null) return <span className="dayBadge neutral">Prazo a revisar</span>;
  if (dias < 0) return <span className="dayBadge risk">Vencido há {Math.abs(dias)}d</span>;
  if (dias === 0) return <span className="dayBadge risk">Vence hoje</span>;
  if (dias === 1) return <span className="dayBadge risk">Vence em 1 dia</span>;
  if (dias <= 3) return <span className="dayBadge today">Vence em {dias} dias</span>;
  return <span className="dayBadge neutral">Vence em {dias} dias</span>;
}

function usaPje(item: ReviewQueueItem): boolean {
  return item.processo?.sistema?.toLowerCase() === "pje";
}

export default function FilaDoDiaView({
  items,
  busy,
  offline,
  onGenerateDraft,
  onOpenEditor,
  onApprove,
  onFile,
  onNavigate
}: {
  items: ReviewQueueItem[];
  busy: string | null;
  offline: boolean;
  onGenerateDraft: (intimacaoId: number) => void;
  onOpenEditor: (peticao: Peticao) => void;
  onApprove: (peticao: Peticao) => void;
  onFile: (peticao: Peticao) => void;
  onNavigate: (view: ViewKey) => void;
}) {
  const [page, setPage] = useState(0);

  const ordered = useMemo(
    () =>
      [...items].sort((a, b) => {
        const pa = prioridade(a);
        const pb = prioridade(b);
        if (pa !== pb) return pa - pb;
        return (a.dias_para_vencer ?? 999) - (b.dias_para_vencer ?? 999);
      }),
    [items]
  );

  // Página sempre válida mesmo quando a lista encolhe após uma ação.
  const pageCount = Math.max(1, Math.ceil(ordered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const visible = ordered.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE);

  function acaoPrincipal(item: ReviewQueueItem) {
    const { peticao, intimacao } = item;
    if (item.status === "cumprido" && !peticao) return null;
    if (peticao?.status === "protocolada") {
      return (
        <button className="toolbarButton" onClick={() => onNavigate("auditoria")}>
          <Table2 size={15} />
          Ver auditoria
        </button>
      );
    }
    if (peticao?.status === "aprovada") {
      return (
        <button
          className="toolbarButton primary"
          disabled={offline || busy === `file-${peticao.id}`}
          onClick={() => onFile(peticao)}
        >
          {busy === `file-${peticao.id}` ? <Loader2 className="spin" size={15} /> : <Send size={15} />}
          {usaPje(item) ? "Preparar PJe" : "Registrar protocolo"}
        </button>
      );
    }
    if (peticao?.status === "em_revisao") {
      return (
        <button
          className="toolbarButton primary"
          disabled={offline || busy === `approve-${peticao.id}`}
          onClick={() => onApprove(peticao)}
        >
          {busy === `approve-${peticao.id}` ? <Loader2 className="spin" size={15} /> : <CheckCircle2 size={15} />}
          Aprovar
        </button>
      );
    }
    if (peticao) {
      return (
        <button className="toolbarButton primary" disabled={offline} onClick={() => onOpenEditor(peticao)}>
          <FilePenLine size={15} />
          Revisar minuta
        </button>
      );
    }
    return (
      <button
        className="toolbarButton primary"
        disabled={offline || busy === `draft-${intimacao.id}`}
        onClick={() => onGenerateDraft(intimacao.id)}
      >
        {busy === `draft-${intimacao.id}` ? <Loader2 className="spin" size={15} /> : <Sparkles size={15} />}
        Gerar minuta
      </button>
    );
  }

  return (
    <section className="filaSurface">
      <p className="surfaceCaption">
        Worklist única priorizada por risco e proximidade do vencimento.
      </p>

      <div className="dataTable filaTable">
        <div className="dataHead" aria-hidden="true">
          <span>Data fatal</span>
          <span>Peça / processo</span>
          <span>Status</span>
          <span className="dataRowEnd">Ação</span>
        </div>
        {visible.map((item) => {
          const peca =
            item.peticao?.tipo ?? item.prazo?.descricao ?? item.intimacao.tipo_comunicacao ?? "Ato a definir";
          const tone = tomDeRisco(item);
          const dataFatal = item.prazo ? formatDate(item.prazo.data_fatal) : null;
          return (
            <article className="dataRow" key={item.intimacao.id}>
              <div
                className={tone ? `filaDate ${tone}` : "filaDate"}
                title={dataFatal ? `Data fatal ${dataFatal}` : "Prazo ainda não calculado"}
              >
                {dataFatal ? (
                  <>
                    <strong>{dataFatal.slice(0, 5)}</strong>
                    <span>{dataFatal.slice(-4)}</span>
                  </>
                ) : (
                  <>
                    <strong>—</strong>
                    <span>s/ prazo</span>
                  </>
                )}
              </div>
              <div className="dataRowMain">
                <strong>{peca}</strong>
                <span className="mono">
                  {item.intimacao.numero_processo ?? item.processo?.numero ?? "Processo não identificado"}
                </span>
              </div>
              <div className="filaMeta">{badgeDePrazo(item)}</div>
              <div className="dataRowEnd">{acaoPrincipal(item)}</div>
            </article>
          );
        })}
        {!ordered.length ? (
          <Empty label="Fila vazia — rode uma captura por OAB ou aguarde novas intimações" />
        ) : null}
      </div>

      <Pagination
        page={safePage}
        pageCount={pageCount}
        totalItems={ordered.length}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        itemLabel="itens"
      />
    </section>
  );
}
