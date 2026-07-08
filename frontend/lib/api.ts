import { supabase } from "./supabase";
import { withAuthHeaders } from "./auth-headers";

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

export type ProximoPrazo = {
  data_fatal: string;
  cumprido: boolean;
  descricao: string | null;
};

/** Processo já cruzado no servidor (`/processos/resumo`): próximo prazo +
 * contagens + campos de busca. A página de Processos monta as linhas a partir
 * disso, sem re-cruzar listas paginadas no cliente. */
export type ProcessoResumo = {
  id: number;
  numero: string;
  classe: string | null;
  tribunal: string | null;
  orgao_julgador: string | null;
  sistema: string | null;
  intimacoes_count: number;
  peticoes_count: number;
  proximo_prazo: ProximoPrazo | null;
  intimacao_tipo: string | null;
  peticao_tipo: string | null;
};

export type ProcessoResumoLista = {
  total: number;
  items: ProcessoResumo[];
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

/** Dossiê de apoio gerado junto com a minuta. Fica separado de `conteudo` (que
 * carrega só o texto da peça) e serve de contexto para a revisão do advogado. */
export type Dossie = {
  contexto_consolidado?: string;
  analise_providencia?: string;
  alertas?: string[];
  confianca?: number;
};

export type Peticao = {
  id: number;
  processo_id: number;
  prazo_id: number | null;
  tipo: string | null;
  conteudo: string | null;
  dossie: Dossie | null;
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

export type Escritorio = {
  id: number;
  nome: string;
  cnpj: string | null;
};

export type OperationalProfile = {
  usuario: Usuario;
  escritorio: Escritorio;
};

export type OperationalProfilePatch = Partial<{
  nome_usuario: string;
  nome_escritorio: string;
  cnpj: string | null;
  oab: string | null;
  oab_uf: string | null;
}>;

export type CurrentUser = {
  usuario_id: number;
  escritorio_id: number;
  email: string;
};

export type OabMonitorada = {
  id: number;
  escritorio_id: number;
  oab: string;
  uf: string;
  ativo: boolean;
  intervalo_horas: number;
  ultima_captura_em: string | null;
  cursor_data: string | null;
};

export type OabRemovalResult = {
  oab_id: number;
  oab: string;
  uf: string;
  purge: boolean;
  removidos: Record<string, number>;
};

export type CredencialAssinatura = {
  id: number;
  usuario_id: number;
  provedor: string;
  tribunal: string | null;
  modo: string;
  referencia_vault: string;
  ativo: boolean;
  created_at: string;
  updated_at: string;
};

/** How the lawyer signs after the robot stops at ready_to_sign. Carries no secret. */
export type SignatureHandoff = {
  provedor: string;
  modo: string;
  mensagem: string;
  instrucoes: string[];
  acoes: string[];
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
  processosResumo?: ProcessoResumoLista;
  reviewQueue?: ReviewQueueItem[];
  operational?: OperationalDashboard;
  backendOffline?: boolean;
};

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000").replace(/\/+$/, "");

// A página de Processos monta a lista a partir de `/processos` (unida ao
// reviewQueue). Com o default de 100, a página não alcançava a base inteira e
// contava menos que o dashboard (200 vs 195), deixando processos fora da tabela.
// 500 é o teto do endpoint (`le=500`); acima disso é preciso paginação real.
const PROCESSOS_PAGE_LIMIT = 500;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const headers = withAuthHeaders(
    {
      "Content-Type": "application/json",
      ...((init?.headers as Record<string, string>) ?? {})
    },
    token
  );
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    cache: "no-store"
  });
  if (response.status === 401) {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Sessão expirada");
  }
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

async function requestList<T>(path: string): Promise<{ data: T[]; failed: boolean }> {
  try {
    return { data: await request<T[]>(path), failed: false };
  } catch (err) {
    console.warn(`Falha ao carregar ${path}`, err);
    return { data: [], failed: true };
  }
}

export async function loadDashboard(): Promise<DashboardData> {
  // Cada lista falha de forma independente: um 500/timeout isolado em UM
  // endpoint nao deve zerar os outros tres (era o que Promise.all fazia antes
  // - uma falha rejeitava tudo e a tela inteira parecia vazia).
  const [intimacoes, processos, prazos, peticoes] = await Promise.all([
    requestList<Intimacao>("/intimacoes"),
    requestList<Processo>(`/processos?limit=${PROCESSOS_PAGE_LIMIT}`),
    requestList<Prazo>("/prazos"),
    requestList<Peticao>("/peticoes")
  ]);
  const [operational, reviewQueue, processosResumo] = await Promise.all([
    requestOptional<OperationalDashboard>("/dashboard/operational"),
    requestOptional<ReviewQueueItem[]>("/review/queue"),
    requestOptional<ProcessoResumoLista>("/processos/resumo")
  ]);
  // So sinaliza "backend indisponivel" quando as quatro listas nucleares
  // falharam juntas -- sintoma real de backend fora do ar, nao um erro isolado.
  const backendOffline = [intimacoes, processos, prazos, peticoes].every((r) => r.failed);
  return {
    intimacoes: intimacoes.data,
    processos: processos.data,
    prazos: prazos.data,
    peticoes: peticoes.data,
    processosResumo,
    operational,
    reviewQueue,
    backendOffline
  };
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

/** Protocolo assíncrono: PJe assistido até ready_to_sign; demais conectores usam registro controlado. */
export async function protocolarPeticaoAsync(
  peticaoId: number,
  credencialId?: number
): Promise<JobExecucao> {
  return request<JobExecucao>(`/peticoes/${peticaoId}/protocolar/async`, {
    method: "POST",
    body: JSON.stringify(credencialId != null ? { credencial_id: credencialId } : {})
  });
}

export async function confirmarProtocoloManual(
  peticaoId: number,
  protocolo: string,
  comprovanteUri?: string,
  credencialId?: number
): Promise<Peticao> {
  return request<Peticao>(`/peticoes/${peticaoId}/protocolar/confirmar`, {
    method: "POST",
    body: JSON.stringify({
      protocolo,
      ...(comprovanteUri ? { comprovante_uri: comprovanteUri } : {}),
      ...(credencialId != null ? { credencial_id: credencialId } : {})
    })
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

export async function listarOabsMonitoradas(): Promise<OabMonitorada[]> {
  return request<OabMonitorada[]>("/capturas/oab");
}

export async function listarUsuarios(escritorioId?: number): Promise<Usuario[]> {
  const qs = escritorioId != null ? `?escritorio_id=${escritorioId}` : "";
  return request<Usuario[]>(`/usuarios${qs}`);
}

export async function carregarPerfilOperacional(): Promise<OperationalProfile> {
  return request<OperationalProfile>("/settings/profile");
}

export async function atualizarPerfilOperacional(
  patch: OperationalProfilePatch
): Promise<OperationalProfile> {
  return request<OperationalProfile>("/settings/profile", {
    method: "PATCH",
    body: JSON.stringify(patch)
  });
}

let currentUserCache: CurrentUser | null = null;

export async function carregarUsuarioAtual(): Promise<CurrentUser> {
  if (currentUserCache != null) return currentUserCache;
  currentUserCache = await request<CurrentUser>("/me");
  return currentUserCache;
}

export async function resolverUsuarioAtual(): Promise<number> {
  return (await carregarUsuarioAtual()).usuario_id;
}

export async function resolverEscritorioAtual(): Promise<number> {
  return (await carregarUsuarioAtual()).escritorio_id;
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

export async function listarTemplates(escritorioId?: number): Promise<TemplatePeticao[]> {
  const id = escritorioId ?? (await resolverEscritorioAtual());
  return request<TemplatePeticao[]>(`/escritorios/${id}/templates-peticao`);
}

export async function criarTemplate(
  template: { tipo: string; area?: string | null; nome: string; conteudo: string; ativo?: boolean },
  escritorioId?: number
): Promise<TemplatePeticao> {
  const id = escritorioId ?? (await resolverEscritorioAtual());
  return request<TemplatePeticao>(`/escritorios/${id}/templates-peticao`, {
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
  await cadastrarOabMonitorada(oab, uf);
  return request<CaptureResult>("/capture/oab", {
    method: "POST",
    body: JSON.stringify({ oab, uf })
  });
}

export async function cadastrarOabMonitorada(
  oab: string,
  uf: string,
  intervaloHoras = 12
): Promise<OabMonitorada> {
  return request<OabMonitorada>("/capturas/oab", {
    method: "POST",
    body: JSON.stringify({ oab, uf, intervalo_horas: intervaloHoras })
  });
}

export async function removerOabMonitorada(
  oabId: number,
  purge = true
): Promise<OabRemovalResult> {
  return request<OabRemovalResult>(`/capturas/oab/${oabId}?purge=${purge ? "true" : "false"}`, {
    method: "DELETE"
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
