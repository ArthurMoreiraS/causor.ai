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
    <section className="moduleGrid">
      {rows.map(({ processo, prazos, intimacoes, peticoes, proximoPrazo }) => (
        <article
          className="recordCard clickable"
          key={processo.id}
          onClick={() => onOpen(processo.id)}
        >
          <header>
            <div>
              <strong className="mono">{processo.numero}</strong>
              <span>{processo.classe ?? "Classe não informada"}</span>
            </div>
            <small>{processo.tribunal ?? "-"}</small>
          </header>
          <div className="recordMeta">
            <span>{processo.orgao_julgador ?? "Órgão não informado"}</span>
            <span>{intimacoes.length} intimações</span>
            <span>{peticoes.length} minutas</span>
            <span className={`pill ${sistemaBadge(processo.sistema).className}`}>
              {sistemaBadge(processo.sistema).label}
            </span>
          </div>
          <div className="recordFooter">
            <div>
              <span>Próximo prazo</span>
              <strong>{proximoPrazo ? formatDate(proximoPrazo.data_fatal) : "-"}</strong>
            </div>
            <DeadlineBadge prazo={proximoPrazo} />
          </div>
          <div className="recordProgress">
            <span style={{ width: `${Math.min(100, prazos.length * 28 + peticoes.length * 18)}%` }} />
          </div>
        </article>
      ))}
      {!rows.length ? <Empty label="Nenhum processo encontrado" /> : null}
    </section>
  );
}
