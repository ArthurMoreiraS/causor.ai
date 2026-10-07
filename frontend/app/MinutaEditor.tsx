"use client";

import { Check, Copy, Download, Loader2, RotateCcw, Save, X } from "lucide-react";
import { useEffect, useState } from "react";
import { baixarPeticaoPdf, baixarFonteCitada, type Peticao, type Prazo, type Processo } from "@/lib/api";
import { humanError } from "@/lib/errors";
import { formatCnj, formatDate } from "@/lib/format";

export default function MinutaEditor({
  peticao,
  processo,
  prazo,
  busy,
  onSave,
  onCreateTask,
  onOpenEvidence,
  onContinue,
  onClose
}: {
  peticao: Peticao;
  processo: Processo | null;
  prazo: Prazo | null;
  busy: boolean;
  onSave: (content: string) => Promise<boolean>;
  onCreateTask?: (alerta: string, index: number) => void;
  onOpenEvidence?: (documentoId: number, versaoId: number, pagina: number) => void;
  onContinue?: () => void;
  onClose: () => void;
}) {
  const serverContent = peticao.conteudo ?? "";
  const [text, setText] = useState(serverContent);
  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);

  const dirty = text !== serverContent;
  const pending = busy || saving;
  const [sourceUrl, setSourceUrl] = useState<string | null>(null);
  useEffect(() => () => {
    if (sourceUrl) URL.revokeObjectURL(sourceUrl.split("#")[0]);
  }, [sourceUrl]);
  useEffect(() => {
    if (!dirty) return;
    const protect = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", protect);
    return () => window.removeEventListener("beforeunload", protect);
  }, [dirty]);
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      const dialogs = document.querySelectorAll('[role="dialog"][aria-modal="true"]');
      if (dialogs[dialogs.length - 1]?.getAttribute("aria-labelledby") !== "minutaEditorTitle") return;
      event.preventDefault();
      if (pending) return;
      if (dirty) setConfirmClose(true);
      else onClose();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [dirty, onClose, pending]);

  function requestClose() {
    if (pending) return;
    if (dirty) setConfirmClose(true);
    else onClose();
  }

  async function save(close = false) {
    if (pending || locked) return;
    setSaving(true);
    setDownloadError(null);
    try {
      if (await onSave(text)) {
        setConfirmClose(false);
        if (close) onClose();
      } else {
        setDownloadError("Não foi possível salvar. Sua edição continua aberta.");
      }
    } catch (err) {
      setDownloadError(humanError(err, "Não foi possível salvar. Sua edição continua aberta."));
    } finally { setSaving(false); }
  }

  async function abrirFonte(doc: number, version: number, page: number) {
    if (onOpenEvidence) { onOpenEvidence(doc, version, page); return; }
    try {
      const blob = await baixarFonteCitada(doc, version);
      setSourceUrl(`${URL.createObjectURL(blob)}#page=${page}`);
    } catch (err) { setDownloadError(humanError(err, "Falha ao abrir a fonte")); }
  }

  async function baixarPdf() {
    setDownloading(true);
    try {
      const blob = await baixarPeticaoPdf(peticao.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `minuta-${processo?.numero ?? peticao.id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setDownloadError(null);
    } catch (err) {
      setDownloadError(humanError(err, "Falha ao baixar o PDF da minuta"));
    } finally {
      setDownloading(false);
    }
  }
  const locked = peticao.status === "protocolada";
  const dossie = peticao.dossie;
  const hasDossie =
    !!dossie &&
    (!!dossie.contexto_consolidado ||
      !!dossie.analise_providencia ||
      (dossie.alertas?.length ?? 0) > 0);

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
    <div className="drawerOverlay" onClick={requestClose}>
      <aside className="detailDrawer wide" role="dialog" aria-modal="true" aria-labelledby="minutaEditorTitle" onClick={(e) => e.stopPropagation()}>
        <header className="detailDrawerHead">
          <span className="sectionKicker">Editor de minuta</span>
          <button className="iconButton" onClick={requestClose} disabled={pending} aria-label="Fechar revisão">
            <X size={15} />
          </button>
        </header>

        <div className="detailBody">
          <h2 className="detailTitle" id="minutaEditorTitle">{peticao.tipo ?? "Petição"}</h2>
          <p className="detailSub">
            {processo?.numero ? formatCnj(processo.numero) : `Processo #${peticao.processo_id}`}
            {prazo ? ` · prazo ${formatDate(prazo.data_fatal)}` : ""}
          </p>

          {confirmClose ? <div className="editorNotice" role="alert">
            <strong>Você tem alterações não salvas.</strong>
            <p>Salve a minuta antes de sair ou descarte o texto alterado.</p>
            <div className="editorFooterLeft">
              <button className="toolbarButton compact" onClick={() => setConfirmClose(false)}>Continuar editando</button>
              <button className="toolbarButton compact" onClick={onClose}>Descartar e sair</button>
              <button className="toolbarButton primary compact" disabled={pending} onClick={() => void save(true)}>Salvar e sair</button>
            </div>
          </div> : null}

          {locked ? (
            <div className="editorNotice">
              <span>Petição protocolada não pode ser editada.</span>
            </div>
          ) : null}

          {hasDossie && dossie ? (
            <section className="dossie">
              <div className="dossieHead">
                <span className="sectionKicker">Dossiê de contexto</span>
                {typeof dossie.confianca === "number" ? (
                  <span className="dossieConfianca">
                    confiança {Math.round(dossie.confianca * 100)}%
                  </span>
                ) : null}
              </div>
              {dossie.contexto_consolidado ? (
                <div className="dossieBlock">
                  <span className="sectionKicker">Contexto consolidado</span>
                  <p>{dossie.contexto_consolidado}</p>
                </div>
              ) : null}
              {dossie.analise_providencia ? (
                <div className="dossieBlock">
                  <span className="sectionKicker">Análise da providência</span>
                  <p>{dossie.analise_providencia}</p>
                </div>
              ) : null}
              {dossie.alertas && dossie.alertas.length > 0 ? (
                <div className="dossieBlock">
                  <span className="sectionKicker">Alertas</span>
                  <ul className="dossieAlertas">
                    {dossie.alertas.map((alerta, i) => (
                      <li key={i}>{alerta}{onCreateTask ? <button type="button" className="toolbarButton compact officeAlertAction" onClick={() => onCreateTask(alerta, i)}>Criar pendência</button> : null}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </section>
          ) : null}

          <label className="srOnly" htmlFor="minutaContent">Conteúdo da minuta</label>
          <textarea
            id="minutaContent"
            className="minutaTextarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            spellCheck
            disabled={locked || pending}
          />

          {!!dossie?.citations?.length && <section aria-label="Fontes enviadas ao redator">
            <h3>Fontes enviadas ao redator</h3>
            {dossie.selecao_contexto && <p>
              {dossie.selecao_contexto.excerpts_selected} de {dossie.selecao_contexto.excerpts_total} excertos
              {" · Inventário e resumos dos documentos preservados."}
            </p>}
            <ul>{dossie.citations.map((citation, index) => <li key={`${citation.chunk_id}-${index}`}>
              <button className="toolbarButton compact" onClick={() => void abrirFonte(citation.documento_id, citation.documento_arquivo_id, citation.pagina)}>
                DOC-{citation.documento_id} · página {citation.pagina}
              </button>
              <blockquote>{citation.quote}</blockquote>
            </li>)}</ul>
            {sourceUrl && <iframe title="Documento citado" src={sourceUrl} style={{ width: "100%", height: 520 }} />}
          </section>}

          <div className="editorFooter">
            <div className="editorFooterLeft">
              <button className="toolbarButton compact" onClick={copy}>
                {copied ? <Check size={14} /> : <Copy size={14} />}
                {copied ? "Copiado" : "Copiar"}
              </button>
              <button
                className="toolbarButton compact"
                disabled={downloading || dirty || pending}
                title={dirty ? "Salve a minuta antes de baixar o PDF" : undefined}
                onClick={() => void baixarPdf()}
              >
                {downloading ? <Loader2 className="spin" size={14} /> : <Download size={14} />}
                Baixar PDF
              </button>
              {dirty ? (
                <button
                  className="toolbarButton compact"
                  onClick={() => { setText(serverContent); setConfirmClose(false); }}
                >
                  <RotateCcw size={14} />
                  Descartar alterações
                </button>
              ) : null}
            </div>
            <div className="editorFooterLeft">
              <button className="toolbarButton primary" disabled={!dirty || locked || pending} onClick={() => void save()}>
                {pending ? <Loader2 className="spin" size={14} /> : <Save size={14} />}
                Salvar minuta
              </button>
              {onContinue && !locked ? <button className="toolbarButton" disabled={dirty || pending} onClick={onContinue}>
                {dossie?.trabalho_id ? "Continuar no trabalho" : "Revisão e aprovação"}
              </button> : null}
            </div>
          </div>
          {downloadError ? (
            <small className="settingsHint vaultError" role="alert">
              {downloadError}
            </small>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
