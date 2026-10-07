"use client";

import { FilePenLine } from "lucide-react";
import type { Peticao } from "@/lib/api";
import { formatCnj, formatDate, sistemaBadge, statusLabel } from "@/lib/format";
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
        Revise e edite o conteúdo das minutas. A aprovação humana acontece em{" "}
        <button className="linkButton" onClick={onGoToGate}>
          Revisão e aprovação
        </button>
        .
      </p>

      <div className="dataTable redactionTable">
        <div className="dataHead" aria-hidden="true">
          <span>Minuta</span>
          <span>Processo</span>
          <span>Situação</span>
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
            <div className="dataRowMain">
              <span className="mono">{processo?.numero ? formatCnj(processo.numero) : `Processo #${peticao.processo_id}`}</span>
              <span>{processo?.tribunal ?? "Tribunal não informado"}</span>
            </div>
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
              <button type="button" className="toolbarButton compact" onClick={(event) => { event.stopPropagation(); onOpenEditor(peticao); }}>
                <FilePenLine size={14} />
                Abrir editor
              </button>
            </div>
          </article>
        ))}
        {!rows.length ? <Empty label="Nenhuma minuta encontrada" /> : null}
      </div>
    </section>
  );
}
