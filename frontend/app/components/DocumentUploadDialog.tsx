"use client";
import { formatCnj } from "@/lib/format";
import { useState, type FormEvent } from "react";
import { enviarAutos, type Processo, type Tarefa } from "@/lib/api";
import { humanError } from "@/lib/errors";
import FilePicker from "./FilePicker";
import { LoadingButton, Modal } from "./ui";

export default function DocumentUploadDialog({ processos, processoId, initialDegree = "1", fixedProcess = false, tarefa, offline, onClose, onSaved }: {
  processos: Processo[]; processoId?: number; initialDegree?: "1" | "2"; fixedProcess?: boolean; tarefa?: Tarefa | null; offline: boolean; onClose: () => void; onSaved: () => void;
}) {
  const [task] = useState(tarefa);
  const [process, setProcess] = useState(String(task?.processo_id || processoId || ""));
  const [degree, setDegree] = useState(initialDegree);
  const [files, setFiles] = useState<File[]>([]);
  const [summaryProfile, setSummaryProfile] = useState<"padrao" | "aprofundada">("padrao");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const options = processos.filter(p => !task?.cliente_id || p.cliente_id === task.cliente_id);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!process || !files.length || busy || offline) return;
    setBusy(true); setError(null);
    try { await enviarAutos(Number(process), files, degree, { tarefa: task || undefined, perfilResumo: summaryProfile }); onSaved(); }
    catch (err) { setError(humanError(err, "Não foi possível receber os documentos")); }
    finally { setBusy(false); }
  }
  return <Modal className="officeDialog" labelledBy="document-upload-title" onClose={() => { if (!busy) onClose(); }}>
    <form className="officeForm" onSubmit={submit}>
      <h2 id="document-upload-title">Receber documentos</h2>
      {task ? <p className="officeHint">Pendência: {task.titulo}. O recebimento deixa a tarefa em andamento para conferência.</p> : null}
      {error ? <p role="alert" className="officeError">{error}</p> : null}
      <label>Processo de destino<select required value={process} disabled={fixedProcess || Boolean(task?.processo_id) || busy} onChange={e => setProcess(e.target.value)}>
        <option value="">Selecione o processo</option>
        {process && !options.some(p => String(p.id) === process) ? <option value={process}>{task?.processo_numero || `Processo #${process}`}</option> : null}
        {options.map(p => <option key={p.id} value={p.id}>{formatCnj(p.numero)}</option>)}
      </select></label>
      <label>Grau de destino<select value={degree} disabled={busy} onChange={e => setDegree(e.target.value as "1" | "2")}>
        <option value="1">1º grau</option><option value="2">2º grau</option>
      </select></label>
      <FilePicker label="Arquivos PDF" kind="PDFs" accept="application/pdf,.pdf" multiple disabled={busy}
        files={files} onChange={setFiles} hint="Um ou vários arquivos, até 50 por envio." />
      <label>Resumo dos documentos<select value={summaryProfile} disabled={busy}
        onChange={e => setSummaryProfile(e.target.value as "padrao" | "aprofundada")}>
        <option value="padrao">Padrão</option><option value="aprofundada">Aprofundado</option>
      </select></label>
      <p className="officeHint">Use aprofundado para peças complexas: pode levar mais tempo e consumir mais créditos de IA. A escolha vale para novos documentos; arquivos idênticos já resumidos mantêm o resultado existente.</p>
      <p className="officeHint">Os arquivos serão acrescentados ao conjunto existente deste grau. Reenviar o mesmo nome cria uma versão do documento. As versões anteriores permanecem disponíveis.</p>
      <p className="officeHint">O envio registra os documentos fornecidos por você; a íntegra do tribunal e a suficiência das provas precisam ser conferidas.</p>
      <div className="modalActions"><button type="button" className="toolbarButton" disabled={busy} onClick={onClose}>Cancelar</button>
        <LoadingButton type="submit" loading={busy} disabled={offline || !process || !files.length || files.length > 50}>Enviar documentos</LoadingButton></div>
      {files.length > 50 ? <p role="alert">Envie até 50 arquivos por vez.</p> : null}
    </form>
  </Modal>;
}
