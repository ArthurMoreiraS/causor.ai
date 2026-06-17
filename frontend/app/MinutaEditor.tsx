"use client";

import { Check, Copy, Loader2, RotateCcw, Save, X } from "lucide-react";
import { useState } from "react";
import type { Peticao, Prazo, Processo } from "@/lib/api";
import { formatDate } from "@/lib/format";

export default function MinutaEditor({
  peticao,
  processo,
  prazo,
  busy,
  onSave,
  onClose
}: {
  peticao: Peticao;
  processo: Processo | null;
  prazo: Prazo | null;
  busy: boolean;
  onSave: (content: string) => void;
  onClose: () => void;
}) {
  const serverContent = peticao.conteudo ?? "";
  const [text, setText] = useState(serverContent);
  const [copied, setCopied] = useState(false);

  const dirty = text !== serverContent;
  const locked = peticao.status === "protocolada";

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard may be blocked */
    }
  }

  return (
    <div className="drawerOverlay" onClick={onClose}>
      <aside className="detailDrawer wide" onClick={(e) => e.stopPropagation()}>
        <header className="detailDrawerHead">
          <span className="sectionKicker">Editor de minuta</span>
          <button className="iconButton" onClick={onClose} aria-label="Fechar">
            <X size={15} />
          </button>
        </header>

        <div className="detailBody">
          <h2 className="detailTitle">{peticao.tipo ?? "Petição"}</h2>
          <p className="detailSub">
            {processo?.numero ?? `Processo #${peticao.processo_id}`}
            {prazo ? ` · prazo ${formatDate(prazo.data_fatal)}` : ""}
          </p>

          {locked ? (
            <div className="editorNotice">
              <span>Petição protocolada não pode ser editada.</span>
            </div>
          ) : null}

          <textarea
            className="minutaTextarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            spellCheck
            disabled={locked}
          />

          <div className="editorFooter">
            <div className="editorFooterLeft">
              <button className="toolbarButton compact" onClick={copy}>
                {copied ? <Check size={14} /> : <Copy size={14} />}
                {copied ? "Copiado" : "Copiar"}
              </button>
              {dirty ? (
                <button
                  className="toolbarButton compact"
                  onClick={() => setText(serverContent)}
                >
                  <RotateCcw size={14} />
                  Descartar alterações
                </button>
              ) : null}
            </div>
            <button
              className="toolbarButton primary"
              disabled={!dirty || locked || busy}
              onClick={() => onSave(text)}
            >
              {busy ? <Loader2 className="spin" size={14} /> : <Save size={14} />}
              Salvar minuta
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}
