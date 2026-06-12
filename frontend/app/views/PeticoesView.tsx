"use client";

import { FilePenLine } from "lucide-react";
import type { Peticao } from "@/lib/api";
import { formatDate, statusLabel } from "@/lib/format";
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
      <div className="redactionIntro">
        <FilePenLine size={16} />
        <div>
          <strong>Espaço de redação</strong>
          <span>
            Revise e edite o conteúdo das minutas. A aprovação e o protocolo acontecem no{" "}
            <button className="linkButton" onClick={onGoToGate}>
              Gate OAB
            </button>
            .
          </span>
        </div>
      </div>

      <div className="redactionList">
        {rows.map(({ peticao, processo, prazo }) => {
          const content = peticao.conteudo ?? "Sem conteúdo";
          return (
            <article
              className="redactionCard clickable"
              key={peticao.id}
              onClick={() => onOpenEditor(peticao)}
            >
              <header>
                <div>
                  <strong>{peticao.tipo ?? "Petição"}</strong>
                  <span className="mono">{processo?.numero ?? `Processo #${peticao.processo_id}`}</span>
                </div>
                <div className="redactionTags">
                  <span className={`pill ${peticao.status}`}>{statusLabel(peticao.status)}</span>
                </div>
              </header>
              <p className="redactionPreview">{content}</p>
              <footer className="redactionFoot">
                <span>{prazo ? `Prazo: ${formatDate(prazo.data_fatal)}` : "Sem prazo vinculado"}</span>
                <span className="redactionOpen">
                  <FilePenLine size={14} />
                  Abrir editor
                </span>
              </footer>
            </article>
          );
        })}
        {!rows.length ? <Empty label="Nenhuma minuta encontrada" /> : null}
      </div>
    </section>
  );
}
