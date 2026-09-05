"use client";

import { useEffect, useState } from "react";
import { Check, Plus, RefreshCw } from "lucide-react";
import { atualizarTarefa, listarTarefas, type Tarefa, type TarefaStatus } from "@/lib/api";
import { humanError } from "@/lib/errors";
import { formatDate } from "@/lib/format";
import { TASK_STATUSES, TASK_TYPES } from "../components/TarefaDialog";
import { EmptyState, LoadingButton } from "../components/ui";

export default function TarefasView({ offline, refreshKey, onNew, onEdit, onOpenProcess, onOpenNotice, onOpenDraft }: {
  offline: boolean; refreshKey: number; onNew: () => void; onEdit: (task: Tarefa) => void;
  onOpenProcess: (id: number) => void; onOpenNotice: (id: number) => void; onOpenDraft: (id: number) => void;
}) {
  const [items, setItems] = useState<Tarefa[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<TarefaStatus | "">("");
  const [offset, setOffset] = useState(0);
  const [tick, setTick] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  useEffect(() => {
    let active = true;
    if (offline) { setLoading(false); return; }
    setLoading(true);
    const timer = setTimeout(() => {
      listarTarefas({ q: query, status: status || undefined, offset, limit: 30 }).then(page => {
        if (active) { setItems(page.items); setTotal(page.total); setError(null); }
      }).catch(err => { if (active) { setItems([]); setTotal(0); setError(humanError(err, "Falha ao carregar tarefas")); } })
        .finally(() => { if (active) setLoading(false); });
    }, 200);
    return () => { active = false; clearTimeout(timer); };
  }, [offline, refreshKey, tick, query, status, offset]);
  async function finish(task: Tarefa) {
    if (busy !== null || offline) return;
    setBusy(task.id);
    try {
      await atualizarTarefa(task.id, { versao: task.versao, status: "concluida" });
      setTick(v => v + 1);
    } catch (err) { setError(humanError(err, "Não foi possível concluir a tarefa")); }
    finally { setBusy(null); }
  }
  async function changeStatus(task: Tarefa, next: TarefaStatus) {
    setBusy(task.id);
    try { await atualizarTarefa(task.id, { versao: task.versao, status: next }); setTick(v => v + 1); }
    catch (err) { setError(humanError(err, "Não foi possível alterar a tarefa")); }
    finally { setBusy(null); }
  }
  return <section className="officeSurface">
    <header className="officeHead"><div><h1>Tarefas e pendências</h1><p>Providências, documentos e revisões com contexto e responsável.</p></div>
      <button className="toolbarButton" disabled={offline} onClick={onNew}><Plus size={16} />Nova tarefa</button></header>
    <div className="officeToolbar">
      <label>Buscar tarefas<input value={query} onChange={e => { setQuery(e.target.value); setOffset(0); }} placeholder="Título ou descrição" /></label>
      <label>Situação<select value={status} onChange={e => { setStatus(e.target.value as TarefaStatus | ""); setOffset(0); }}>
        <option value="">Todas</option>{Object.entries(TASK_STATUSES).map(([key, value]) => <option key={key} value={key}>{value}</option>)}
      </select></label>
      <button className="toolbarButton" onClick={() => setTick(v => v + 1)} disabled={loading || offline}><RefreshCw size={14} />Atualizar</button>
    </div>
    {offline ? <p role="alert" className="officeError">Conecte-se ao servidor para consultar e atualizar tarefas.</p> : null}
    {error ? <p role="alert" className="officeError">{error}</p> : null}
    {loading ? <p role="status">Carregando tarefas…</p> : null}
    <div className="officeList" aria-busy={loading}>
      {items.map(task => <article className="officeItem" key={task.id}>
        <div className="officeItemHead"><div><span className="sectionKicker">{TASK_TYPES[task.tipo]} · {task.prioridade}</span>
          <h2>{task.titulo}</h2></div><label className="officeStatus"><span className="sr-only">Situação de {task.titulo}</span>
          <select value={task.status} disabled={busy !== null || offline || loading} onChange={e => void changeStatus(task, e.target.value as TarefaStatus)}>
            {Object.entries(TASK_STATUSES).map(([key, value]) => <option key={key} value={key}>{value}</option>)}
          </select></label></div>
        {task.descricao ? <p className="officeDescription">{task.descricao}</p> : null}
        <div className="officeMeta"><span>{task.responsavel_nome || "Sem responsável"}</span>
          <span>Data interna: {task.data_prevista ? formatDate(task.data_prevista) : "não definida"}</span>
          {task.cliente_nome ? <span>{task.cliente_nome}</span> : null}</div>
        {task.origem_texto ? <details className="officeOrigin"><summary>Alerta que originou a pendência</summary><p>{task.origem_texto}</p></details> : null}
        <div className="officeActions">
          {task.processo_id ? <button className="toolbarButton compact" onClick={() => onOpenProcess(task.processo_id!)}>{task.processo_numero || "Abrir processo"}</button> : null}
          {task.intimacao_id ? <button className="toolbarButton compact" onClick={() => onOpenNotice(task.intimacao_id!)}>Intimação de origem</button> : null}
          {task.peticao_id ? <button className="toolbarButton compact" onClick={() => onOpenDraft(task.peticao_id!)}>Minuta de origem</button> : null}
          <button className="toolbarButton compact" disabled={offline || busy !== null || loading} onClick={() => onEdit(task)}>Editar</button>
          {!(["concluida", "cancelada"].includes(task.status)) ? <LoadingButton className="toolbarButton compact" loading={busy === task.id}
            disabled={offline || busy !== null || loading} icon={<Check size={14} />} onClick={() => void finish(task)}>Concluir</LoadingButton> : null}
        </div>
      </article>)}
      {!items.length && !loading && !error && !offline ? <EmptyState title="Nenhuma tarefa encontrada" description="Crie uma providência aqui ou transforme um alerta da minuta em uma pendência." /> : null}
    </div>
    <footer className="officePagination"><span>{total} tarefas · {items.length ? offset + 1 : 0}–{offset + items.length}</span>
      <button className="toolbarButton compact" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - 30))}>Anterior</button>
      <button className="toolbarButton compact" disabled={offset + 30 >= total || loading} onClick={() => setOffset(offset + 30)}>Próxima</button>
    </footer>
  </section>;
}
