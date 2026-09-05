"use client";

import { useEffect, useState, type FormEvent } from "react";
import { atualizarTarefa, criarTarefa, listarUsuarios, type Processo, type Tarefa, type TarefaInput, type Usuario } from "@/lib/api";
import { humanError } from "@/lib/errors";
import { LoadingButton, Modal } from "./ui";

export const TASK_TYPES = { providencia: "Providência", documento: "Documento pendente", revisao: "Revisão", atendimento: "Atendimento" } as const;
export const TASK_STATUSES = { aberta: "Aberta", em_andamento: "Em andamento", aguardando: "Aguardando", concluida: "Concluída", cancelada: "Cancelada" } as const;

export default function TarefaDialog({ initial, task, contextLabel, processos, offline, onClose, onSaved }: {
  initial: TarefaInput; task?: Tarefa; contextLabel?: string; processos: Processo[]; offline: boolean;
  onClose: () => void; onSaved: (task: Tarefa) => void;
}) {
  const [form, setForm] = useState<TarefaInput>({ tipo: "providencia", prioridade: "normal", ...initial });
  const [users, setUsers] = useState<Usuario[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usersError, setUsersError] = useState(false);
  useEffect(() => {
    let active = true;
    listarUsuarios().then(value => { if (active) setUsers(value); }).catch(() => { if (active) setUsersError(true); });
    return () => { active = false; };
  }, []);
  function change<K extends keyof TarefaInput>(key: K, value: TarefaInput[K]) {
    setForm(prev => ({ ...prev, [key]: value }));
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy || offline || !form.titulo.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const fields = { titulo: form.titulo.trim(), descricao: form.descricao?.trim() || null,
        tipo: form.tipo, prioridade: form.prioridade, data_prevista: form.data_prevista || null,
        responsavel_id: form.responsavel_id ?? null };
      const saved = task ? await atualizarTarefa(task.id, { ...fields, versao: task.versao }) : await criarTarefa({ ...form, ...fields });
      onSaved(saved);
    } catch (err) {
      setError(humanError(err, "Não foi possível salvar a tarefa"));
    } finally { setBusy(false); }
  }
  const close = () => { if (!busy) onClose(); };
  const lockedSource = Boolean(task || initial.intimacao_id || initial.peticao_id);
  const options = processos.filter(p => !initial.cliente_id || p.cliente_id === initial.cliente_id);
  return <Modal onClose={close} labelledBy="task-dialog-title" className="officeDialog">
    <form onSubmit={save} className="officeForm">
      <div><h2 id="task-dialog-title">{task ? "Editar tarefa" : "Nova tarefa"}</h2>
        <p className="officeHint">{contextLabel || task?.cliente_nome || "Organize a próxima ação do escritório."}</p></div>
      {initial.alerta_texto_esperado ? <blockquote className="officeSource">{initial.alerta_texto_esperado}</blockquote> : null}
      {error ? <p role="alert" className="officeError">{error}</p> : null}
      <label>Título<input required maxLength={255} value={form.titulo} onChange={e => change("titulo", e.target.value)} /></label>
      <label>Descrição<textarea maxLength={10000} rows={3} value={form.descricao ?? ""} onChange={e => change("descricao", e.target.value)} /></label>
      <div className="officeFormGrid">
        <label>Tipo<select value={form.tipo} onChange={e => change("tipo", e.target.value as TarefaInput["tipo"])}>
          {Object.entries(TASK_TYPES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        <label>Prioridade<select value={form.prioridade} onChange={e => change("prioridade", e.target.value as TarefaInput["prioridade"])}>
          <option value="normal">Normal</option><option value="alta">Alta</option><option value="urgente">Urgente</option>
        </select></label>
        <label>Data interna (opcional)<input type="date" value={form.data_prevista ?? ""} onChange={e => change("data_prevista", e.target.value || null)} /></label>
        <label>Responsável<select value={form.responsavel_id ?? ""} disabled={usersError} onChange={e => change("responsavel_id", e.target.value ? Number(e.target.value) : null)}>
          <option value="">Sem responsável</option>
          {form.responsavel_id && !users.some(u => u.id === form.responsavel_id) ? <option value={form.responsavel_id}>{task?.responsavel_nome || "Responsável atual"}</option> : null}
          {users.map(u => <option key={u.id} value={u.id}>{u.nome}</option>)}
        </select></label>
      </div>
      <p className="officeHint">A data interna organiza o trabalho. O prazo judicial continua sendo conferido no módulo Prazos.</p>
      {usersError ? <p role="status" className="officeHint">Não foi possível carregar a equipe. O responsável atual será preservado.</p> : null}
      <label>Processo<select disabled={lockedSource} value={form.processo_id ?? ""} onChange={e => change("processo_id", e.target.value ? Number(e.target.value) : null)}>
        <option value="">{initial.intimacao_id && !form.processo_id ? "Vínculo definido pela intimação de origem" : "Sem processo vinculado"}</option>
        {form.processo_id && !options.some(p => p.id === form.processo_id) ? <option value={form.processo_id}>{task?.processo_numero || "Processo de origem"}</option> : null}
        {options.map(p => <option key={p.id} value={p.id}>{p.numero}</option>)}
      </select></label>
      <div className="modalActions">
        <button type="button" className="toolbarButton" onClick={close} disabled={busy}>Cancelar</button>
        <LoadingButton type="submit" loading={busy} disabled={offline || !form.titulo.trim()}>{task ? "Salvar tarefa" : "Criar tarefa"}</LoadingButton>
      </div>
    </form>
  </Modal>;
}
