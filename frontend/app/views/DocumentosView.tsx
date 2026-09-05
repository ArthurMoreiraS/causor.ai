"use client";
import { useEffect, useState } from "react";
import { listarDocumentos, listarDocumentosTarefa, obterTarefa, type DocumentoBiblioteca, type DocumentoRecebido, type Processo, type Tarefa } from "@/lib/api";
import { humanError } from "@/lib/errors";
import DocumentEvidenceDialog, { documentStatus } from "../components/DocumentEvidenceDialog";
import DocumentUploadDialog from "../components/DocumentUploadDialog";
import ProcessContextStatus from "../components/ProcessContextStatus";
import { EmptyState } from "../components/ui";

export default function DocumentosView({ processos, offline, initialProcessId, initialTask, onChanged, onTasks, onAll }: {
  processos: Processo[]; offline: boolean; initialProcessId?: number; initialTask?: Tarefa | null;
  onChanged: () => void; onTasks: () => void; onAll: () => void;
}) {
  const [processId, setProcessId] = useState(String(initialTask?.processo_id || initialProcessId || ""));
  const [task, setTask] = useState(initialTask);
  const [receipts, setReceipts] = useState<DocumentoRecebido[]>([]);
  const [items, setItems] = useState<DocumentoBiblioteca[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [tick, setTick] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [taskError, setTaskError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [taskLoading, setTaskLoading] = useState(Boolean(initialTask));
  const [upload, setUpload] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<{ id: number; name: string; version?: number } | null>(null);
  const receivingDisabled = offline || taskLoading || Boolean(taskError) || task?.status === "concluida" || task?.status === "cancelada";
  useEffect(() => {
    if (offline) { setLoading(false); return; }
    let active = true;
    setLoading(true);
    async function load() {
      try {
        const result = await listarDocumentos({ processo_id: processId ? Number(processId) : undefined, q: query, offset, limit: 30 });
        if (active) { setItems(result.items); setTotal(result.total); setError(null); }
      } catch (err) { if (active) { setItems([]); setTotal(0); setError(humanError(err, "Falha ao carregar documentos")); } }
      finally { if (active) setLoading(false); }
    }
    const timer = setTimeout(() => void load(), 200);
    const poll = setInterval(() => void load(), 8000);
    return () => { active = false; clearTimeout(timer); clearInterval(poll); };
  }, [offline, processId, query, offset, tick]);
  useEffect(() => {
    if (!initialTask || offline) return;
    let active = true;
    setTaskLoading(true);
    Promise.all([obterTarefa(initialTask.id), listarDocumentosTarefa(initialTask.id)]).then(([current, files]) => {
      if (active) { setTask(current); setReceipts(files); setTaskError(null); if (current.processo_id) setProcessId(String(current.processo_id)); }
    }).catch(err => { if (active) setTaskError(humanError(err, "Falha ao atualizar a pendência")); })
      .finally(() => { if (active) setTaskLoading(false); });
    return () => { active = false; };
  }, [initialTask, offline, tick]);
  return <section className="officeSurface">
    <header className="officeHead"><div><h1>Documentos e evidências</h1><p>Arquivos, versões e fontes para conferir o contexto das minutas.</p></div>
      <button className="toolbarButton" disabled={receivingDisabled}
        onClick={() => setUpload(true)}>Receber documentos</button></header>
    {notice ? <p role="status" className="officeNotice">{notice}</p> : null}
    {offline ? <p role="alert" className="officeError">Conecte-se ao servidor para consultar e receber documentos.</p> : null}
    {task ? <section className="officePanel documentTaskPanel"><div className="officeItemHead"><div><span className="sectionKicker">Documentos da pendência</span><h2>{task.titulo}</h2></div>
      <button className="toolbarButton" onClick={onTasks}>Voltar às tarefas</button></div>
      <p className="officeHint">Confira os arquivos recebidos antes de concluir a tarefa. A conclusão não aprova a minuta nem comprova a suficiência dos documentos.</p>
      {taskError ? <p role="alert" className="officeError">{taskError}</p> : null}
      {taskLoading ? <p role="status">Atualizando pendência…</p> : null}
      {receipts.map(r => <div key={r.id} className="documentReceipt"><span>{r.nome} · recebido em {new Date(r.created_at).toLocaleString("pt-BR")}</span>
        {r.documento_id && r.documento_arquivo_id ? <button className="toolbarButton compact" onClick={() => setEvidence({ id: r.documento_id!, name: r.nome, version: r.documento_arquivo_id! })}>Conferir versão recebida</button>
          : <span className="officeHint">Registro de recebimento preservado; arquivo desvinculado.</span>}</div>)}
      {!receipts.length && !taskLoading && !taskError ? <p className="officeHint">Nenhum documento recebido nesta pendência.</p> : null}
      <button className="toolbarButton compact" onClick={onAll}>Abrir biblioteca geral</button>
    </section> : null}
    <div className="officeToolbar"><label>Processo<select value={processId} disabled={Boolean(task?.processo_id)} onChange={e => { setProcessId(e.target.value); setOffset(0); }}>
      <option value="">Todos os processos</option>
      {processId && !processos.some(p => String(p.id) === processId) ? <option value={processId}>{task?.processo_numero || `Processo #${processId}`}</option> : null}
      {processos.map(p => <option key={p.id} value={p.id}>{p.numero}</option>)}
    </select></label><label>Buscar documento<input value={query} placeholder="Nome do arquivo" maxLength={200} onChange={e => { setQuery(e.target.value); setOffset(0); }} /></label>
      <button className="toolbarButton" disabled={offline || loading} onClick={() => setTick(v => v + 1)}>Atualizar</button></div>
    {processId && !offline ? <ProcessContextStatus key={`${processId}-${tick}`} processoId={Number(processId)}
      onReceiveDocuments={() => setUpload(true)} receivingDisabled={receivingDisabled} /> : null}
    {error ? <p role="alert" className="officeError">{error}</p> : null}
    {loading ? <p role="status">Carregando documentos…</p> : null}
    <div className="officeList" aria-busy={loading}>
      {items.map(doc => <article className="officeItem" key={doc.id}><div className="officeItemHead"><div>
        <span className="sectionKicker">{doc.processo_numero || "Sem processo"}{doc.grau ? ` · ${doc.grau}º grau` : ""}</span><h2>{doc.nome}</h2></div>
        <button className="toolbarButton" disabled={offline} onClick={() => setEvidence({ id: doc.id, name: doc.nome, version: doc.versao?.id })}>Conferir evidências</button></div>
        <div className="officeMeta">{doc.cliente_nome ? <span>{doc.cliente_nome}</span> : null}
          <span>{doc.versao ? documentStatus(doc.versao.extracao, doc.versao.resumo_status) : "Sem arquivo verificado"}</span><span>{doc.versao?.paginas ?? "—"} páginas</span></div>
        <p className="officeHint">{doc.no_contexto ? "Incluído no conjunto atual de documentos. Confira o processamento e as fontes antes de usar na minuta." : "Fora do conjunto atual de documentos. Disponível para consulta histórica."}</p>
      </article>)}
      {!items.length && !loading && !error && !offline ? <EmptyState title="Nenhum documento encontrado" description="Receba os arquivos do processo para iniciar a análise ou ajuste a busca." /> : null}
    </div>
    <footer className="officePagination"><span>{total} documentos</span><button className="toolbarButton compact" disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 30))}>Anterior</button>
      <button className="toolbarButton compact" disabled={loading || offset + 30 >= total} onClick={() => setOffset(offset + 30)}>Próxima</button></footer>
    {upload ? <DocumentUploadDialog processos={processos} processoId={processId ? Number(processId) : undefined} tarefa={task} offline={offline} onClose={() => setUpload(false)}
      onSaved={() => { setUpload(false); setTick(v => v + 1); onChanged(); setNotice("Documentos recebidos. O processamento atualizará o contexto; confira os resultados antes de revisar a próxima minuta."); }} /> : null}
    {evidence ? <DocumentEvidenceDialog key={`${evidence.id}-${evidence.version}`} documentoId={evidence.id} nome={evidence.name} versaoId={evidence.version} onClose={() => setEvidence(null)} /> : null}
  </section>;
}
