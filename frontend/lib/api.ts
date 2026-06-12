export type Intimacao = {
  id: number;
  processo_id: number | null;
  fonte: string;
  numero_processo: string | null;
  tribunal: string | null;
  tipo_comunicacao: string | null;
  teor: string | null;
  data_disponibilizacao: string | null;
  data_publicacao: string | null;
};

export type Processo = {
  id: number;
  numero: string;
  classe: string | null;
  tribunal: string | null;
  orgao_julgador: string | null;
  sistema: string | null;
};

export type Prazo = {
  id: number;
  processo_id: number | null;
  intimacao_id: number | null;
  descricao: string | null;
  data_inicio: string;
  dias: number;
  dias_uteis: boolean;
  data_fatal: string;
  cumprido: boolean;
};

export type Peticao = {
  id: number;
  processo_id: number;
  prazo_id: number | null;
  tipo: string | null;
  conteudo: string | null;
  status: "rascunho" | "em_revisao" | "aprovada" | "protocolada" | string;
  aprovada_por: number | null;
  protocolada_em: string | null;
};

export type DashboardMetric = {
  key: string;
  label: string;
  value: number;
};

export type WorkflowStep = {
  key: string;
  label: string;
  detail: string;
  status: string;
};

export type ConnectorStatus = {
  key: string;
  name: string;
  detail: string;
  status: string;
};

export type AuditSignal = {
  key: string;
  title: string;
  detail: string;
};

export type OperationalDashboard = {
  metrics: DashboardMetric[];
  workflow: WorkflowStep[];
  connectors: ConnectorStatus[];
  audit_signals: AuditSignal[];
};

export type CaptureResult = {
  intimacoes_novas: number;
  processos_enriquecidos: number;
  prazos_registrados: number;
};

export type ReviewQueueItem = {
  intimacao: Intimacao;
  processo: Processo | null;
  prazo: Prazo | null;
  peticao: Peticao | null;
  status: string;
  risco: string;
  dias_para_vencer: number | null;
};

export type ProposedAction = {
  tipo: string;
  label: string;
  endpoint: string;
  metodo: string;
  payload: Record<string, unknown>;
};

export type ChatTurn = { role: "user" | "assistant"; content: string };

export type ChatResponse = {
  reply: string;
  proposed_actions: ProposedAction[];
  tool_trace: { ferramenta: string; input: Record<string, unknown> }[];
};

export type AuditLog = {
  id: number;
  ator: string;
  acao: string;
  entidade: string | null;
  entidade_id: number | null;
  detalhe: Record<string, unknown> | null;
  created_at: string;
};

export type Classificacao = {
  tipo: string;
  peticao_sugerida: string;
  prazo_dias: number;
  dias_uteis: boolean;
  confianca: number;
  resumo: string;
};

export type AlertaPrazo = {
  prazo_id: number;
  processo_id: number | null;
  processo_numero: string | null;
  descricao: string | null;
  data_fatal: string;
  dias_para_vencer: number;
  nivel: "vencido" | "d0" | "d1" | "d3";
};

export type JobExecucao = {
  id: number;
  tipo: string;
  status: "queued" | "running" | "completed" | "failed" | string;
  entidade: string | null;
  entidade_id: number | null;
  payload: Record<string, unknown> | null;
  resultado: Record<string, unknown> | null;
  erro: string | null;
  created_at: string;
  updated_at: string;
};

export type Usuario = {
  id: number;
  escritorio_id: number;
  nome: string;
  email: string | null;
  oab: string | null;
  oab_uf: string | null;
};

export type CredencialAssinatura = {
  id: number;
  usuario_id: number;
  provedor: string;
  referencia_vault: string;
  ativo: boolean;
  created_at: string;
  updated_at: string;
};

export type TemplatePeticao = {
  id: number;
  escritorio_id: number;
  tipo: string;
  area: string | null;
  nome: string;
  conteudo: string;
  ativo: boolean;
  created_at: string;
  updated_at: string;
};

export type DashboardData = {
  intimacoes: Intimacao[];
  processos: Processo[];
  prazos: Prazo[];
  peticoes: Peticao[];
  reviewQueue?: ReviewQueueItem[];
  operational?: OperationalDashboard;
  backendOffline?: boolean;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function requestOptional<T>(path: string): Promise<T | undefined> {
  try {
    return await request<T>(path);
  } catch (err) {
    console.warn(`Endpoint opcional indisponível: ${path}`, err);
    return undefined;
  }
}

export async function loadDashboard(): Promise<DashboardData> {
  try {
    const [intimacoes, processos, prazos, peticoes] = await Promise.all([
      request<Intimacao[]>("/intimacoes"),
      request<Processo[]>("/processos"),
      request<Prazo[]>("/prazos"),
      request<Peticao[]>("/peticoes")
    ]);
    const [operational, reviewQueue] = await Promise.all([
      requestOptional<OperationalDashboard>("/dashboard/operational"),
      requestOptional<ReviewQueueItem[]>("/review/queue")
    ]);
    // Backend reachable: reflect its real state (even when empty).
    // Optional aggregate endpoints may be absent during local development; the
    // UI can derive those surfaces from core data.
    return {
      intimacoes,
      processos,
      prazos,
      peticoes,
      operational,
      reviewQueue
    };
  } catch (err) {
    console.warn(`Backend indisponível em ${API_BASE}`, err);
    return {
      intimacoes: [],
      processos: [],
      prazos: [],
      peticoes: [],
      backendOffline: true
    };
  }
}

export async function gerarMinuta(
  intimacaoId: number,
  calendarYears?: number[]
): Promise<Classificacao | null> {
  const body = calendarYears?.length ? { calendar_years: calendarYears } : {};
  const resp = await request<{ classificacao: Classificacao }>(
    `/intimacoes/${intimacaoId}/draft`,
    { method: "POST", body: JSON.stringify(body) }
  );
  return resp.classificacao;
}

export async function editarPeticao(
  peticaoId: number,
  patch: { conteudo?: string; status?: "rascunho" | "em_revisao" }
): Promise<Peticao> {
  const usuarioId = await resolverUsuarioAtual();
  return request<Peticao>(`/peticoes/${peticaoId}`, {
    method: "PATCH",
    body: JSON.stringify({ usuario_id: usuarioId, ...patch })
  });
}

export async function aprovarPeticao(peticaoId: number): Promise<void> {
  const usuarioId = await resolverUsuarioAtual();
  await request(`/peticoes/${peticaoId}/approve`, {
    method: "POST",
    body: JSON.stringify({ usuario_id: usuarioId })
  });
}

export async function protocolarPeticao(peticaoId: number): Promise<void> {
  await request(`/peticoes/${peticaoId}/protocolar`, { method: "POST" });
}

/** Protocolo simulado via job assíncrono — retorna o job com comprovante. */
export async function protocolarPeticaoAsync(
  peticaoId: number,
  credencialId?: number
): Promise<JobExecucao> {
  return request<JobExecucao>(`/peticoes/${peticaoId}/protocolar/async`, {
    method: "POST",
    body: JSON.stringify(credencialId != null ? { credencial_id: credencialId } : {})
  });
}

export async function listarJobs(filtros?: {
  tipo?: string;
  status?: string;
}): Promise<JobExecucao[]> {
  const params = new URLSearchParams();
  if (filtros?.tipo) params.set("tipo", filtros.tipo);
  if (filtros?.status) params.set("status", filtros.status);
  const qs = params.toString();
  return request<JobExecucao[]>(`/jobs${qs ? `?${qs}` : ""}`);
}

export async function carregarAlertas(): Promise<AlertaPrazo[]> {
  return request<AlertaPrazo[]>("/alertas");
}

export async function listarUsuarios(escritorioId?: number): Promise<Usuario[]> {
  const qs = escritorioId != null ? `?escritorio_id=${escritorioId}` : "";
  return request<Usuario[]>(`/usuarios${qs}`);
}

// A demo roda single-tenant sem auth: o "usuário logado" é o primeiro usuário
// do banco (a seed recria usuários com ids novos, então nada pode ser fixo).
let usuarioAtualId: number | null = null;

export async function resolverUsuarioAtual(): Promise<number> {
  if (usuarioAtualId != null) return usuarioAtualId;
  try {
    const usuarios = await listarUsuarios();
    usuarioAtualId = usuarios[0]?.id ?? 1;
  } catch {
    usuarioAtualId = 1;
  }
  return usuarioAtualId;
}

export async function listarCredenciais(usuarioId?: number): Promise<CredencialAssinatura[]> {
  const id = usuarioId ?? (await resolverUsuarioAtual());
  return request<CredencialAssinatura[]>(`/usuarios/${id}/credenciais-assinatura`);
}

export async function cadastrarCredencial(
  provedor: string,
  referenciaExterna: string,
  usuarioId?: number
): Promise<CredencialAssinatura> {
  const id = usuarioId ?? (await resolverUsuarioAtual());
  return request<CredencialAssinatura>(`/usuarios/${id}/credenciais-assinatura`, {
    method: "POST",
    body: JSON.stringify({ provedor, referencia_externa: referenciaExterna })
  });
}

export async function desativarCredencial(credencialId: number): Promise<CredencialAssinatura> {
  return request<CredencialAssinatura>(`/credenciais-assinatura/${credencialId}/desativar`, {
    method: "PATCH"
  });
}

export async function listarTemplates(escritorioId = 1): Promise<TemplatePeticao[]> {
  return request<TemplatePeticao[]>(`/escritorios/${escritorioId}/templates-peticao`);
}

export async function criarTemplate(
  template: { tipo: string; area?: string | null; nome: string; conteudo: string; ativo?: boolean },
  escritorioId = 1
): Promise<TemplatePeticao> {
  return request<TemplatePeticao>(`/escritorios/${escritorioId}/templates-peticao`, {
    method: "POST",
    body: JSON.stringify(template)
  });
}

export async function atualizarTemplate(
  templateId: number,
  patch: Partial<{ tipo: string; area: string | null; nome: string; conteudo: string; ativo: boolean }>
): Promise<TemplatePeticao> {
  return request<TemplatePeticao>(`/templates-peticao/${templateId}`, {
    method: "PATCH",
    body: JSON.stringify(patch)
  });
}

export async function cumprirPrazo(prazoId: number): Promise<void> {
  const usuarioId = await resolverUsuarioAtual();
  await request(`/prazos/${prazoId}/cumprir`, {
    method: "POST",
    body: JSON.stringify({ usuario_id: usuarioId })
  });
}

export async function enviarMensagemChat(
  messages: ChatTurn[],
  processoId?: number
): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ messages, processo_id: processoId ?? null })
  });
}

export async function rodarCapturaOab(
  oab: string,
  uf: string
): Promise<CaptureResult> {
  return request<CaptureResult>("/capture/oab", {
    method: "POST",
    body: JSON.stringify({ oab, uf })
  });
}

export async function revisarPrazo(
  prazoId: number,
  patch: Partial<Pick<Prazo, "descricao" | "dias" | "dias_uteis" | "data_inicio" | "data_fatal">>
): Promise<Prazo> {
  const usuarioId = await resolverUsuarioAtual();
  return request<Prazo>(`/prazos/${prazoId}`, {
    method: "PATCH",
    body: JSON.stringify({ usuario_id: usuarioId, ...patch })
  });
}

export async function carregarAuditoria(filtros?: {
  entidade?: string;
  entidade_id?: number;
}): Promise<AuditLog[]> {
  const params = new URLSearchParams();
  if (filtros?.entidade) params.set("entidade", filtros.entidade);
  if (filtros?.entidade_id != null) params.set("entidade_id", String(filtros.entidade_id));
  const qs = params.toString();
  return request<AuditLog[]>(`/audit${qs ? `?${qs}` : ""}`);
}
