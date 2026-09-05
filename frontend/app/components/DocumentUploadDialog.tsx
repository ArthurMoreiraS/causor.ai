"use client";
import { useState, type FormEvent } from "react";
import { enviarAutos, type Processo, type Tarefa } from "@/lib/api";
import { humanError } from "@/lib/errors";
import { LoadingButton, Modal } from "./ui";

export default function DocumentUploadDialog({ processos, processoId, tarefa, offline, onClose, onSaved }: {
  processos: Processo[]; processoId?: number; tarefa?: Tarefa | null; offline: boolean; onClose: () => void; onSaved: () => void;
}) {
  const [task] = useState(tarefa);
  const [process, setProcess] = useState(String(task?.processo_id || processoId || ""));
  const [degree, setDegree] = useState("1");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const options = processos.filter(p => !task?.cliente_id || p.cliente_id === task.cliente_id);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!process || !files.length || busy || offline) return;
    setBusy(true); setError(null);
    try { await enviarAutos(Number(process), files, degree, { tarefa: task || undefined }); onSaved(); }
    catch (err) { setError(humanError(err, "Não foi possível receber os documentos")); }
    finally { setBusy(false); }
  }
  return <Modal className="officeDialog" labelledBy="document-upload-title" onClose={() => { if (!busy) onClose(); }}>
    <form className="officeForm" onSubmit={submit}>
      <h2 id="document-upload-title">Receber documentos</h2>
      {task ? <p className="officeHint">Pendência: {task.titulo}. O recebimento deixa a tarefa em andamento para conferência.</p> : null}
      {error ? <p role="alert" className="officeError">{error}</p> : null}
      <label>Processo de destino<select required value={process} disabled={Boolean(task?.processo_id) || busy} onChange={e => setProcess(e.target.value)}>
        <option value="">Selecione o processo</option>
        {process && !options.some(p => String(p.id) === process) ? <option value={process}>{task?.processo_numero || `Processo #${process}`}</option> : null}
        {options.map(p => <option key={p.id} value={p.id}>{p.numero}</option>)}
      </select></label>
      <label>Grau de destino<select value={degree} disabled={busy} onChange={e => setDegree(e.target.value)}>
        <option value="1">1º grau</option><option value="2">2º grau</option>
      </select></label>
      <label>Arquivos PDF<input type="file" accept="application/pdf,.pdf" multiple required disabled={busy}
        onChange={e => setFiles(Array.from(e.target.files || []))} /></label>
      <p className="officeHint">Os arquivos serão acrescentados ao conjunto existente deste grau. Reenviar o mesmo nome cria uma versão do documento. As versões anteriores permanecem disponíveis.</p>
      <p className="officeHint">O envio registra os documentos fornecidos por você; a íntegra do tribunal e a suficiência das provas precisam ser conferidas.</p>
      <div className="modalActions"><button type="button" className="toolbarButton" disabled={busy} onClick={onClose}>Cancelar</button>
        <LoadingButton type="submit" loading={busy} disabled={offline || !process || !files.length || files.length > 50}>Enviar documentos</LoadingButton></div>
      {files.length > 50 ? <p role="alert">Envie até 50 arquivos por vez.</p> : null}
    </form>
  </Modal>;
}
