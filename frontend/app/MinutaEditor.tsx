"use client";

import { AlertTriangle, Check, Copy, RotateCcw, Save, X } from "lucide-react";
import { useState } from "react";
import type { Peticao, Prazo, Processo } from "@/lib/api";

function formatDate(value: string | null | undefined) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(value));
}

export default function MinutaEditor({
  peticao,
  processo,
  prazo,
  localDraft,
  onSaveLocal,
  onClearLocal,
  onClose
}: {
  peticao: Peticao;
  processo: Processo | null;
  prazo: Prazo | null;
  localDraft: string | undefined;
  onSaveLocal: (content: string) => void;
  onClearLocal: () => void;
  onClose: () => void;
}) {
  const serverContent = peticao.conteudo ?? "";
  const [text, setText] = useState(localDraft ?? serverContent);
  const [copied, setCopied] = useState(false);

  const dirty = text !== (localDraft ?? serverContent);
  const hasLocal = localDraft !== undefined;

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

          <div className="editorNotice">
            <AlertTriangle size={15} />
            <span>
              Edição salva apenas neste navegador. O protocolo continua usando o conteúdo do
              servidor até existir o endpoint de atualização.
            </span>
          </div>

          <textarea
            className="minutaTextarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            spellCheck
          />

          <div className="editorFooter">
            <div className="editorFooterLeft">
              <button className="toolbarButton compact" onClick={copy}>
                {copied ? <Check size={14} /> : <Copy size={14} />}
                {copied ? "Copiado" : "Copiar"}
              </button>
              {hasLocal ? (
                <button
                  className="toolbarButton compact"
                  onClick={() => {
                    onClearLocal();
                    setText(serverContent);
                  }}
                >
                  <RotateCcw size={14} />
                  Descartar edição local
                </button>
              ) : null}
            </div>
            <button
              className="toolbarButton primary"
              disabled={!dirty}
              onClick={() => onSaveLocal(text)}
            >
              <Save size={14} />
              Salvar localmente
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}
