"use client";

import { useEffect, useState } from "react";
import { formatDate, sistemaBadge } from "@/lib/format";
import type { ProcessoRow } from "@/lib/views";
import { DeadlineBadge, Empty } from "../components/ui";

const PAGE_SIZE = 50;

export default function ProcessosView({
  rows,
  total,
  loaded,
  onOpen
}: {
  rows: ProcessoRow[];
  // `total`/`loaded` vêm de /processos/resumo (total real vs. itens carregados).
  total?: number;
  loaded?: number;
  onOpen: (id: number) => void;
}) {
  // Paginação só de renderização: milhares de linhas não vão todas ao DOM.
  const [page, setPage] = useState(0);
  useEffect(() => setPage(0), [rows.length]);

  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const start = safePage * PAGE_SIZE;
  const visible = rows.slice(start, start + PAGE_SIZE);

  // Guarda de honestidade: se o servidor tem mais processos do que os carregados
  // (teto atingido), avisa em vez de fingir o total — a lição do 200 vs 195.
  const capped = total !== undefined && loaded !== undefined && loaded < total;

  return (
    <section className="dataTable processTable">
      <div className="dataHead" aria-hidden="true">
        <span>Processo</span>
        <span>Órgão julgador</span>
        <span>Sistema</span>
        <span>Intimações</span>
        <span>Minutas</span>
        <span>Próximo prazo</span>
      </div>
      {visible.map(({ processo, intimacoesCount, peticoesCount, proximoPrazo }) => (
        <article
          className="dataRow clickable"
          key={processo.id}
          onClick={() => onOpen(processo.id)}
        >
          <div className="dataRowMain">
            <strong className="mono">{processo.numero}</strong>
            <span>{processo.classe ?? "Classe não informada"}</span>
          </div>
          <div className="dataRowMain">
            <strong>{processo.tribunal ?? "-"}</strong>
            <span>{processo.orgao_julgador ?? "Órgão não informado"}</span>
          </div>
          <span
            className={`pill ${sistemaBadge(processo.sistema).className}`}
            title={sistemaBadge(processo.sistema).title}
          >
            {sistemaBadge(processo.sistema).label}
          </span>
          <span className="cellCount">{intimacoesCount}</span>
          <span className="cellCount">{peticoesCount}</span>
          <div className="dataRowEnd">
            <span className="cellDate">
              {proximoPrazo ? formatDate(proximoPrazo.data_fatal) : "—"}
            </span>
            <DeadlineBadge prazo={proximoPrazo} />
          </div>
        </article>
      ))}
      {!rows.length ? <Empty label="Nenhum processo encontrado" /> : null}
      {capped ? (
        <p className="tableNote">
          Exibindo {loaded} de {total} processos. Refine a busca para alcançar o restante.
        </p>
      ) : null}
      {pageCount > 1 ? (
        <div className="tablePager">
          <button
            className="toolbarButton compact"
            disabled={safePage === 0}
            onClick={() => setPage(safePage - 1)}
          >
            Anterior
          </button>
          <span className="pagerStatus">
            {start + 1}–{Math.min(rows.length, start + PAGE_SIZE)} de {rows.length}
          </span>
          <button
            className="toolbarButton compact"
            disabled={safePage >= pageCount - 1}
            onClick={() => setPage(safePage + 1)}
          >
            Próxima
          </button>
        </div>
      ) : null}
    </section>
  );
}
