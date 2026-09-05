"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Plus, RefreshCw, Users } from "lucide-react";
import { criarCliente, listarClientes, vincularCliente, type Cliente, type Processo, type TarefaInput } from "@/lib/api";
import { humanError } from "@/lib/errors";
import { EmptyState, LoadingButton, Modal } from "../components/ui";

export default function ClientesView({ offline, processos, refreshKey, onChanged, onOpenProcess, onNewTask }: {
  offline: boolean; processos: Processo[]; refreshKey: number; onChanged: () => void;
  onOpenProcess: (id: number) => void; onNewTask: (input: TarefaInput, context?: string) => void;
}) {
  const [items, setItems] = useState<Cliente[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [tick, setTick] = useState(0);
  const [selected, setSelected] = useState<Cliente | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [document, setDocument] = useState("");
  const [processId, setProcessId] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [linkMessage, setLinkMessage] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    if (offline) { setLoading(false); return; }
    setLoading(true);
    const timer = setTimeout(() => {
      listarClientes({ q: query, limit: 30, offset }).then(page => {
        if (active) { setItems(page.items); setTotal(page.total); setError(null); }
      }).catch(err => { if (active) { setItems([]); setTotal(0); setError(humanError(err, "Falha ao carregar clientes")); } })
        .finally(() => { if (active) setLoading(false); });
    }, 200);
    return () => { active = false; clearTimeout(timer); };
  }, [query, offset, refreshKey, tick, offline]);
  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy || offline || !name.trim()) return;
    setBusy(true); setFormError(null);
    try {
      const customer = await criarCliente({ nome: name.trim(), documento: document.trim() || null });
      setSelected(customer); setCreating(false); setName(""); setDocument(""); setQuery(""); setOffset(0); setTick(v => v + 1);
    } catch (err) { setFormError(humanError(err, "Não foi possível cadastrar o cliente")); }
    finally { setBusy(false); }
  }
  async function link(event: FormEvent) {
    event.preventDefault();
    if (!selected || !processId || busy || offline) return;
    setBusy(true); setError(null); setLinkMessage(null);
    try {
      await vincularCliente(Number(processId), selected.id);
      setProcessId(""); setTick(v => v + 1); onChanged();
      setLinkMessage("Cliente vinculado. As próximas minutas usarão essa parte representada; confira as minutas existentes.");
    } catch (err) { setError(humanError(err, "Não foi possível vincular o processo")); }
    finally { setBusy(false); }
  }
  const linked = selected ? processos.filter(p => p.cliente_id === selected.id) : [];
  return <section className="officeSurface">
    <header className="officeHead"><div><h1>Clientes</h1><p>Conecte cada cliente aos processos e às próximas providências.</p></div>
      <button className="toolbarButton" disabled={offline} onClick={() => { setFormError(null); setCreating(true); }}><Plus size={16} />Novo cliente</button></header>
    <div className="officeToolbar"><label>Buscar cliente<input value={query} placeholder="Nome do cliente" onChange={e => { setQuery(e.target.value); setOffset(0); }} /></label>
      <button className="toolbarButton" disabled={loading || offline} onClick={() => setTick(v => v + 1)}><RefreshCw size={14} />Atualizar</button></div>
    {error ? <p role="alert" className="officeError">{error}</p> : null}
    {offline ? <p role="alert" className="officeError">Conecte-se ao servidor para consultar os clientes.</p> : null}
    {linkMessage ? <p role="status" className="officeNotice">{linkMessage}</p> : null}
    {loading ? <p role="status">Carregando clientes…</p> : null}
    <div className="officeColumns">
      <div className="officeList" aria-busy={loading}>
        {items.map(customer => <button className={`officeClient${selected?.id === customer.id ? " selected" : ""}`} key={customer.id}
          aria-pressed={selected?.id === customer.id} onClick={() => { setSelected(customer); setProcessId(""); setLinkMessage(null); }}>
          <Users size={18} /><span><strong>{customer.nome}</strong><small>{customer.processos_count} processos vinculados</small></span>
        </button>)}
        {!items.length && !loading && !error && !offline ? <EmptyState title="Nenhum cliente encontrado" description="Cadastre o cliente e vincule seus processos para identificar a parte representada." /> : null}
        <footer className="officePagination"><span>{total} clientes</span>
          <button className="toolbarButton compact" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - 30))}>Anterior</button>
          <button className="toolbarButton compact" disabled={offset + 30 >= total || loading} onClick={() => setOffset(offset + 30)}>Próxima</button>
        </footer>
      </div>
      <section className="officePanel">
        {selected ? <><span className="sectionKicker">Cliente selecionado</span><h2>{selected.nome}</h2>
          <p className="officeHint">Documento: {selected.documento || "não informado"}</p>
          <button className="toolbarButton" disabled={offline} onClick={() => onNewTask({ titulo: "", cliente_id: selected.id, tipo: "atendimento" }, selected.nome)}><Plus size={14} />Nova tarefa para este cliente</button>
          <h3>Processos vinculados</h3>
          {linked.map(process => <button key={process.id} className="officeProcessLink" onClick={() => onOpenProcess(process.id)}>{process.numero}<small>{process.tribunal || "Tribunal não informado"}</small></button>)}
          {!linked.length ? <p className="officeHint">Nenhum processo vinculado na carteira carregada.</p> : null}
          <form className="officeForm" onSubmit={link}>
            <label>Vincular processo<select value={processId} onChange={e => setProcessId(e.target.value)}>
              <option value="">Escolha um processo sem cliente</option>
              {processos.filter(p => !p.cliente_id).map(p => <option key={p.id} value={p.id}>{p.numero}</option>)}
            </select></label>
            <LoadingButton type="submit" loading={busy} disabled={offline || !processId}>Vincular cliente representado</LoadingButton>
          </form>
        </> : <EmptyState title="Abra a ficha de um cliente" description="Consulte os processos e crie tarefas de atendimento, documentos ou revisão." />}
      </section>
    </div>
    {creating ? <Modal onClose={() => { if (!busy) setCreating(false); }} labelledBy="new-client-title" className="officeDialog">
      <form onSubmit={save} className="officeForm"><h2 id="new-client-title">Novo cliente</h2>
        {formError ? <p role="alert" className="officeError">{formError}</p> : null}
        <label>Nome ou razão social<input required maxLength={255} value={name} onChange={e => setName(e.target.value)} /></label>
        <label>CPF/CNPJ (opcional)<input maxLength={20} value={document} onChange={e => setDocument(e.target.value)} /></label>
        <div className="modalActions"><button type="button" className="toolbarButton" disabled={busy} onClick={() => setCreating(false)}>Cancelar</button>
          <LoadingButton type="submit" loading={busy} disabled={offline || !name.trim()}>Cadastrar cliente</LoadingButton></div>
      </form>
    </Modal> : null}
  </section>;
}
