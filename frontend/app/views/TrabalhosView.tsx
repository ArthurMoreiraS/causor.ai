"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { criarCliente, listarClientes, type Cliente, type Processo } from "@/lib/api";
import { atualizarTrabalho, criarProcesso, criarTrabalho, listarTrabalhos, obterTrabalho, type Trabalho } from "@/lib/work-api";
import { humanError } from "@/lib/errors";
import ProcessContextStatus from "../components/ProcessContextStatus";
import DocumentUploadDialog from "../components/DocumentUploadDialog";
import WorkEvidence from "../components/WorkEvidence";
import WorkScope from "../components/WorkScope";
import WorkAssistant from "../components/WorkAssistant";
import { LoadingButton } from "../components/ui";

export default function TrabalhosView({ processos, offline, initialProcessId, initialOrigin, onChanged, onDocuments, onOpenDraft, onUnsavedChange, onRouteChange, refreshKey = 0, focusOnOpen = false }: {
  processos: Processo[]; offline: boolean; initialProcessId?: number; initialOrigin?: { intimacaoId: number; prazoId: number | null }; onChanged: () => void;
  onDocuments: (id: number) => void; onOpenDraft: (id: number) => void;
  onUnsavedChange?: (dirty: boolean) => void;
  onRouteChange?: () => void;
  refreshKey?: number;
  focusOnOpen?: boolean;
}) {
  const [works, setWorks] = useState<Trabalho[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [work, setWork] = useState<Trabalho | null>(null);
  const [origin, setOrigin] = useState(initialOrigin);
  const [clients, setClients] = useState<Cliente[]>([]);
  const [clientQuery, setClientQuery] = useState("");
  const [process, setProcess] = useState(String(initialProcessId || ""));
  const [localProcess, setLocalProcess] = useState<Processo | null>(null);
  const [newProcess, setNewProcess] = useState(false);
  const [number, setNumber] = useState("");
  const [court, setCourt] = useState("");
  const [client, setClient] = useState("");
  const [newClientName, setNewClientName] = useState("");
  const [purpose, setPurpose] = useState("");
  const [instructions, setInstructions] = useState("");
  const [degree, setDegree] = useState<"1" | "2">("1");
  const [party, setParty] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [receiving, setReceiving] = useState(false);
  const [revision, setRevision] = useState(0);
  const selectionVersion = useRef(0);
  const unsavedRef = useRef(false);
  const formRef = useRef<HTMLFormElement>(null);
  const processOptions = localProcess && !processos.some(p => p.id === localProcess.id) ? [localProcess, ...processos] : processos;
  const dirty = Boolean(work && (purpose !== work.providencia || instructions !== work.instrucoes || degree !== work.grau || party !== (work.polo || "")));
  const unsaved = dirty || (!work && Boolean(purpose || instructions || party || number || court || client || clientQuery || newClientName || newProcess || (process && process !== String(initialProcessId || "")) || degree !== "1"));
  unsavedRef.current = unsaved;
  useEffect(() => { onUnsavedChange?.(unsaved); }, [onUnsavedChange, unsaved]);
  useEffect(() => {
    if (!unsaved) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [unsaved]);

  const selectWork = useCallback((value: Trabalho | null, force = false) => {
    if (!force && unsavedRef.current && !window.confirm("Há alterações não salvas. Descartar e continuar?")) return false;
    selectionVersion.current += 1;
    setOrigin(undefined);
    setWork(value); setPurpose(value?.providencia || ""); setInstructions(value?.instrucoes || "");
    setDegree(value?.grau === "2" ? "2" : "1"); setParty(value?.polo || "");
    setProcess(String(value?.processo_id || "")); setError(null); setNewProcess(false);
    setNumber(""); setCourt(""); setClient(""); setClientQuery(""); setNewClientName("");
    const url = new URL(window.location.href);
    if (value) url.searchParams.set("trabalho", String(value.id)); else url.searchParams.delete("trabalho");
    url.searchParams.delete("novo");
    url.searchParams.delete("processo");
    url.searchParams.delete("intimacao");
    url.searchParams.delete("prazo");
    window.history.replaceState(null, "", url);
    onRouteChange?.();
    return true;
  }, [onRouteChange]);

  function startNewWork() {
    if (!selectWork(null)) return;
    setError(null);
    const url = new URL(window.location.href); url.searchParams.set("novo", "1"); window.history.replaceState(null, "", url);
    formRef.current?.scrollIntoView?.({ block: "start" });
    formRef.current?.focus({ preventScroll: true });
  }

  useEffect(() => { if (focusOnOpen) formRef.current?.focus({ preventScroll: true }); }, [focusOnOpen]);

  useEffect(() => {
    let active = true;
    listarTrabalhos(initialProcessId, offset).then(result => {
      if (active) { setWorks(result.items); setTotal(result.total); }
    }).catch(err => { if (active) setError(humanError(err, "Falha ao listar trabalhos")); });
    return () => { active = false; };
  }, [initialProcessId, offset, revision]);
  useEffect(() => {
    let active = true;
    listarClientes({ q: clientQuery, limit: 50 }).then(result => { if (active) setClients(result.items); })
      .catch(err => { if (active) setError(humanError(err, "Falha ao consultar clientes")); });
    return () => { active = false; };
  }, [clientQuery]);
  useEffect(() => {
    let active = true;
    const version = selectionVersion.current;
    const id = Number(new URLSearchParams(window.location.search).get("trabalho"));
    if (id > 0) obterTrabalho(id).then(value => {
      if (active && version === selectionVersion.current && !unsavedRef.current) selectWork(value, true);
    })
      .catch(err => { if (active && version === selectionVersion.current) setError(humanError(err, "Não foi possível retomar o trabalho")); });
    return () => { active = false; };
  }, [selectWork]);
  useEffect(() => {
    const id = work?.id;
    if (!id || offline) return;
    let active = true;
    const version = selectionVersion.current;
    const reload = () => obterTrabalho(id).then(value => {
      if (!active || version !== selectionVersion.current) return;
      if (dirty) {
        if (value.versao !== work.versao) setError("Este trabalho foi alterado em outra sessão. Confira a versão antes de salvar.");
      } else if (value.versao !== work.versao) {
        selectWork(value, true);
      } else {
        setWork(old => old?.id === id ? value : old);
      }
    }).catch(() => { /* The next explicit action still enforces the current version. */ });
    void reload();
    const timer = setInterval(reload, 15000);
    return () => { active = false; clearInterval(timer); };
  }, [work?.id, work?.versao, revision, refreshKey, offline, dirty, selectWork]);
  async function save(event: FormEvent) {
    event.preventDefault(); if (busy || offline) return;
    setBusy(true); setError(null);
    try {
      let processId = Number(process);
      if (newProcess && !work) {
        let clientId = client ? Number(client) : undefined;
        if (!clientId && newClientName.trim()) {
          const createdClient = await criarCliente({ nome: newClientName.trim() });
          clientId = createdClient.id; setClient(String(clientId)); setNewClientName("");
          setClients(items => [...items, createdClient]);
        }
        const created = await criarProcesso({ numero: number, tribunal: court || undefined, cliente_id: clientId });
        setLocalProcess(created); setProcess(String(created.id)); setNewProcess(false); processId = created.id; onChanged();
      }
      const fields = { providencia: purpose, instrucoes: instructions, grau: degree, polo: party || null };
      const result = work ? await atualizarTrabalho(work.id, { ...fields, versao: work.versao })
        : await criarTrabalho({ ...fields, processo_id: processId,
            ...(origin ? { intimacao_id: origin.intimacaoId, prazo_id: origin.prazoId ?? undefined } : {}) });
      selectWork(result, true); setRevision(v => v + 1);
    } catch (err) { setError(humanError(err, "Não foi possível salvar o trabalho")); }
    finally { setBusy(false); }
  }

  function jumpToStage(id: string) {
    const target = document.getElementById(id);
    target?.scrollIntoView({ block: "start" });
    target?.focus({ preventScroll: true });
  }

  return <section className="legalWorkspace" aria-label="Preparar trabalho jurídico">
    <header className="officeToolbar"><div><h2>Preparar trabalho</h2><p>Defina a providência, confira os documentos e as fontes, depois revise a minuta.</p></div>
      <button className="toolbarButton" disabled={busy || offline} onClick={startNewWork}>Novo trabalho</button></header>
    {error ? <p role="alert" className="officeError">{error}</p> : null}
    <div className="legalWorkLayout"><aside className="legalWorkList" aria-label="Trabalhos salvos">
      {works.map(item => <button key={item.id} className={`legalWorkItem ${work?.id === item.id ? "active" : ""}`} disabled={busy}
        onClick={() => selectWork(item)}><strong>{item.providencia}</strong><span>Processo {processOptions.find(p => p.id === item.processo_id)?.numero || `#${item.processo_id || "removido"}`}</span></button>)}
      {!works.length ? <p>Nenhum trabalho salvo neste recorte.</p> : null}
      <div className="tablePager"><button className="toolbarButton" disabled={!offset || busy} onClick={() => setOffset(v => Math.max(0, v - 50))}>Anterior</button>
        <span>{total} trabalhos</span><button className="toolbarButton" disabled={offset + 50 >= total || busy} onClick={() => setOffset(v => v + 50)}>Próximos</button></div>
    </aside><div className="legalWorkBody">
      {work ? <>
        <header className="workContextHeader">
          <strong>{work.providencia}</strong>
          <p>Processo {processOptions.find(item => item.id === work.processo_id)?.numero ?? `#${work.processo_id}`} · {work.grau}º grau · {work.prazo_id ? `Prazo vinculado #${work.prazo_id}` : "Prazo não vinculado"}</p>
        </header>
        <nav className="workStageNavigation" aria-label="Etapas deste trabalho">
          <button type="button" onClick={() => jumpToStage("work-objective")}>Objetivo</button>
          {work.processo_id ? <button type="button" onClick={() => jumpToStage("work-documents")}>Documentos</button> : null}
          {work.processo_id ? <button type="button" onClick={() => jumpToStage("work-evidence")}>Evidências</button> : null}
          {work.evidencias ? <button type="button" onClick={() => jumpToStage("work-draft")}>Minuta</button> : <span>Minuta pendente</span>}
        </nav>
      </> : null}
      <form ref={formRef} id="work-objective" tabIndex={-1} className="officeForm workStageAnchor" onSubmit={save}>
        <h3>{work ? "1. Objetivo e parte representada" : "Novo trabalho · objetivo e parte representada"}</h3>
        {!work && origin ? <p className="officeHint">Intimação #{origin.intimacaoId} vinculada{origin.prazoId ? ` · prazo #${origin.prazoId} a revisar` : " · sem prazo vinculado"}. A providência depende da sua análise.</p> : null}
        {!work ? <label className="workCheckboxLabel"><input type="checkbox" checked={newProcess} disabled={busy} onChange={e => setNewProcess(e.target.checked)} /> Cadastrar processo manualmente</label> : null}
        {newProcess && !work ? <>
          <label>Número CNJ<input required value={number} maxLength={25} disabled={busy} onChange={e => setNumber(e.target.value)} placeholder="0000000-00.0000.0.00.0000" /></label>
          <label>Tribunal informado<input value={court} maxLength={50} disabled={busy} onChange={e => setCourt(e.target.value.toUpperCase())} placeholder="Ex.: TJSP" /></label>
          <label>Buscar cliente<input value={clientQuery} disabled={busy} onChange={e => setClientQuery(e.target.value)} /></label>
          <label>Cliente representado<select value={client} disabled={busy} onChange={e => setClient(e.target.value)}><option value="">Vincular depois na ficha do cliente</option>
            {clients.map(item => <option value={item.id} key={item.id}>{item.nome}</option>)}</select></label>
          {!client ? <label>Ou cadastrar cliente pelo nome<input value={newClientName} maxLength={255} disabled={busy} onChange={e => setNewClientName(e.target.value)} placeholder="Nome da parte representada" /></label> : null}
        </> : <label>Processo<select required value={process} disabled={busy || Boolean(work)} onChange={e => setProcess(e.target.value)}>
          <option value="">Selecione o processo</option>
          {process && !processOptions.some(p => String(p.id) === process) ? <option value={process}>Processo #{process}</option> : null}
          {processOptions.map(p => <option key={p.id} value={p.id}>{p.numero}</option>)}</select></label>}
        <label>Providência<input required minLength={3} maxLength={255} value={purpose} disabled={busy} onChange={e => setPurpose(e.target.value)} placeholder="Ex.: Manifestação sobre o laudo" /></label>
        <label>Instruções para o trabalho<textarea maxLength={20000} rows={4} value={instructions} disabled={busy} onChange={e => setInstructions(e.target.value)} /></label>
        <div className="legalWorkFields"><label>Instância do trabalho<select value={degree} disabled={busy} onChange={e => setDegree(e.target.value as "1" | "2")}><option value="1">1º grau</option><option value="2">2º grau</option></select></label>
          <label>Polo representado<input maxLength={100} value={party} disabled={busy} onChange={e => setParty(e.target.value)} placeholder="Ex.: Autor, réu, interessado" /></label></div>
        <p className="officeHint">{work?.prazo_id ? `Prazo vinculado #${work.prazo_id}.` : "Prazo não vinculado. Nenhuma data de vencimento será presumida."}</p>
        <LoadingButton type="submit" loading={busy} disabled={offline || (!newProcess && !process) || !purpose.trim()}>{work ? "Salvar objetivo" : "Criar trabalho"}</LoadingButton>
      </form>
      {work?.processo_id ? <section id="work-documents" tabIndex={-1} className="legalWorkStage workStageAnchor"><h3>2. Documentos e contexto</h3>
        <p>Envie os autos e os documentos do cliente. A cobertura do tribunal permanece declarada por quem envia.</p>
        <ProcessContextStatus key={`context-${work.processo_id}-${revision}`} processoId={work.processo_id} onReceiveDocuments={() => setReceiving(true)} receivingDisabled={offline} assistedOnly />
        <button className="toolbarButton" onClick={() => onDocuments(work.processo_id!)}>Conferir documentos e fontes</button>
        <WorkScope key={`scope-${work.id}-${revision}`} work={work} disabled={offline || busy || dirty}
          onSaved={value => { setWork(value); setRevision(v => v + 1); }} />
      </section> : null}
      {work?.peticao_id ? <section className="legalWorkStage"><h3>Minuta vinculada</h3><button className="toolbarButton" onClick={() => onOpenDraft(work.peticao_id!)}>Abrir minuta para revisão</button></section> : null}
      {work?.processo_id ? <WorkEvidence key={`evidence-${work.id}`} work={work} disabled={offline || busy || purpose !== work.providencia || instructions !== work.instrucoes || degree !== work.grau || party !== (work.polo || "")}
        onSaved={value => { setWork(value); setRevision(v => v + 1); onChanged(); }} onOpenDraft={onOpenDraft} /> : null}
      {work && !work.processo_id ? <p role="status">O processo foi removido. O histórico deste trabalho foi preservado.</p> : null}
      {dirty ? <p role="status">Salve o objetivo alterado antes de continuar as etapas do trabalho.</p> : null}
      {work?.processo_id ? <WorkAssistant key={`assistant-${work.id}`} work={work} disabled={offline || busy || dirty} /> : null}
    </div></div>
    {receiving && work?.processo_id ? <DocumentUploadDialog processos={processOptions} processoId={work.processo_id} offline={offline}
      onClose={() => setReceiving(false)} onSaved={() => { setReceiving(false); setRevision(v => v + 1); onChanged(); }} /> : null}
  </section>;
}
