"use client";

import { formatDate, sistemaBadge } from "@/lib/format";
import type { ProcessoRow } from "@/lib/views";
import { DeadlineBadge, Empty } from "../components/ui";

export default function ProcessosView({
  rows,
  onOpen
}: {
  rows: ProcessoRow[];
  onOpen: (id: number) => void;
}) {
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
      {rows.map(({ processo, intimacoes, peticoes, proximoPrazo }) => (
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
          <span className={`pill ${sistemaBadge(processo.sistema).className}`}>
            {sistemaBadge(processo.sistema).label}
          </span>
          <span className="cellCount">{intimacoes.length}</span>
          <span className="cellCount">{peticoes.length}</span>
          <div className="dataRowEnd">
            <span className="cellDate">
              {proximoPrazo ? formatDate(proximoPrazo.data_fatal) : "—"}
            </span>
            <DeadlineBadge prazo={proximoPrazo} />
          </div>
        </article>
      ))}
      {!rows.length ? <Empty label="Nenhum processo encontrado" /> : null}
    </section>
  );
}
