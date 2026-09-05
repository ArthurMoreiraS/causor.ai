"use client";

import { FilePenLine } from "lucide-react";
import type { Peticao } from "@/lib/api";
import { formatDate, sistemaBadge, statusLabel } from "@/lib/format";
import type { PeticaoRow } from "@/lib/views";
import { Empty } from "../components/ui";

export default function PeticoesView({
  rows,
  onOpenEditor,
  onGoToGate
}: {
  rows: PeticaoRow[];
  onOpenEditor: (peticao: Peticao) => void;
  onGoToGate: () => void;
}) {
  return (
    <section className="redactionBoard">
      <p className="surfaceCaption">
        Revise e edite o conteúdo das minutas. A aprovação e o protocolo acontecem no{" "}
        <button className="linkButton" onClick={onGoToGate}>
          Revisão e aprovação
        </button>
        .
      </p>

      <div className="dataTable redactionTable">
        <div className="dataHead" aria-hidden="true">
          <span>Minuta</span>
          <span>Processo</span>
          <span>Status</span>
          <span>Sistema</span>
          <span>Prazo</span>
          <span className="dataRowEnd">Ação</span>
        </div>
        {rows.map(({ peticao, processo, prazo }) => (
          <article
            className="dataRow clickable"
            key={peticao.id}
            onClick={() => onOpenEditor(peticao)}
          >
            <div className="dataRowMain">
              <strong>{peticao.tipo ?? "Petição"}</strong>
              <span>{peticao.conteudo ?? "Sem conteúdo"}</span>
            </div>
            <span className="cellDate mono">
              {processo?.numero ?? `Processo #${peticao.processo_id}`}
            </span>
            <span className={`pill ${peticao.status}`}>{statusLabel(peticao.status)}</span>
            <span
              className={`pill ${sistemaBadge(processo?.sistema).className}`}
              title={sistemaBadge(processo?.sistema).title}
            >
              {sistemaBadge(processo?.sistema).label}
            </span>
            <span className="cellDate">
              {prazo ? formatDate(prazo.data_fatal) : "—"}
            </span>
            <div className="dataRowEnd">
              <span className="redactionOpen">
                <FilePenLine size={14} />
                Abrir editor
              </span>
            </div>
          </article>
        ))}
        {!rows.length ? <Empty label="Nenhuma minuta encontrada" /> : null}
      </div>
    </section>
  );
}
