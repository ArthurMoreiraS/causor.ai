"use client";

import { Loader2, MessageCircle, Sparkles } from "lucide-react";
import { formatDate, statusLabel } from "@/lib/format";
import type { IntimacaoRow } from "@/lib/views";
import { DeadlineBadge, Empty } from "../components/ui";

export default function IntimacoesView({
  rows,
  busy,
  offline,
  onOpen,
  onGenerateDraft
}: {
  rows: IntimacaoRow[];
  busy: string | null;
  offline: boolean;
  onOpen: (intimacaoId: number) => void;
  onGenerateDraft: (intimacaoId: number) => void;
}) {
  return (
    <section className="inboxList">
      {rows.map(({ intimacao, processo, prazo, peticao }) => (
        <article className="inboxItem clickable" key={intimacao.id} onClick={() => onOpen(intimacao.id)}>
          <div className="inboxMarker">
            <MessageCircle size={15} />
          </div>
          <div className="inboxContent">
            <header>
              <div>
                <strong>{intimacao.tipo_comunicacao ?? "Comunicação judicial"}</strong>
                <span className="mono">{intimacao.numero_processo ?? processo?.numero ?? "Processo não identificado"}</span>
              </div>
              <small>{formatDate(intimacao.data_publicacao ?? intimacao.data_disponibilizacao)}</small>
            </header>
            <p>{intimacao.teor ?? "Teor não informado"}</p>
            <div className="inboxMeta">
              <span>{intimacao.tribunal ?? processo?.tribunal ?? "-"}</span>
              <DeadlineBadge prazo={prazo} />
              <span className={`queueStatus ${peticao?.status ?? "capturada"}`}>
                {peticao ? statusLabel(peticao.status) : "Sem minuta"}
              </span>
            </div>
          </div>
          <button
            className="toolbarButton"
            disabled={busy === `draft-${intimacao.id}` || offline}
            onClick={(e) => {
              e.stopPropagation();
              onGenerateDraft(intimacao.id);
            }}
          >
            {busy === `draft-${intimacao.id}` ? <Loader2 className="spin" size={15} /> : <Sparkles size={15} />}
            Minutar
          </button>
        </article>
      ))}
      {!rows.length ? <Empty label="Nenhuma intimação encontrada" /> : null}
    </section>
  );
}
