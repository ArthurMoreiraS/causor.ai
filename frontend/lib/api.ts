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
  prazo_analise?: PrazoAnalise | null;
};

/** Providência cabível sugerida pelo tipo de ato, com data já calculada. */
export type PrazoAlternativa = { ato_cabivel: string; dias: number; fundamento: string; fonte: string; data_fatal: string };

export type PrazoAnalise = {
  status: string; job_id?: number; motivo?: string | null; prazo_id?: number; dias?: number | null; unidade?: string;
  publicacao?: string; primeiro_dia?: string; data_fatal?: string; evidencia?: string | null; fundamento?: string | null;
  calendario?: string; ato?: string; rito?: string; origem_duracao?: string | null; alternativas?: PrazoAlternativa[];
};

export type Processo = {
  id: number;
  cliente_id?: number | null;
  numero: string;
  classe: string | null;
  tribunal: string | null;
  orgao_julgador: string | null;
  sistema: string | null;
};

export type Cliente = { id: number; nome: string; documento: string | null; processos_count: number };
export type TarefaStatus = "aberta" | "em_andamento" | "aguardando" | "concluida" | "cancelada";
export type TarefaTipo = "providencia" | "documento" | "revisao" | "atendimento";
export type TarefaInput = {
  titulo: string; descricao?: string | null; tipo?: TarefaTipo; prioridade?: "normal" | "alta" | "urgente";
  data_prevista?: string | null; processo_id?: number | null; cliente_id?: number | null;
  intimacao_id?: number | null; peticao_id?: number | null; alerta_indice?: number | null;
  alerta_texto_esperado?: string | null; responsavel_id?: number | null;
};
export type Tarefa = TarefaInput & {
  trabalho_id?: number | null;
  id: number; tipo: TarefaTipo; status: TarefaStatus; prioridade: "normal" | "alta" | "urgente";
  versao: number; origem: string; origem_texto: string | null; concluida_em: string | null;
  processo_numero: string | null; cliente_nome: string | null; responsavel_nome: string | null;
};
export type TarefaPatch = Partial<Pick<TarefaInput, "titulo" | "descricao" | "tipo" | "prioridade" | "data_prevista" | "responsavel_id">> & {
  versao: number; status?: TarefaStatus;
};
export type Pagina<T> = { total: number; items: T[] };

export function listarClientes(params: { q?: string; limit?: number; offset?: number } = {}): Promise<Pagina<Cliente>> {
  return request(`/clientes?${new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]))}`);
}
export function criarCliente(payload: { nome: string; documento?: string | null }): Promise<Cliente> {
  return request("/clientes", { method: "POST", body: JSON.stringify(payload) });
}
export type ClienteExcluido = { cliente_id: number; processos_desvinculados: number; tarefas_desvinculadas: number };
export function excluirCliente(clienteId: number): Promise<ClienteExcluido> {
  return request(`/clientes/${clienteId}`, { method: "DELETE" });
}
export function vincularCliente(processoId: number, clienteId: number | null): Promise<{ processo_id: number; cliente_id: number | null }> {
  return request(`/processos/${processoId}/cliente`, { method: "PUT", body: JSON.stringify({ cliente_id: clienteId }) });
}
export function listarTarefas(params: { q?: string; status?: TarefaStatus; processo_id?: number; cliente_id?: number; responsavel_id?: number; limit?: number; offset?: number } = {}): Promise<Pagina<Tarefa>> {
  return request(`/tarefas?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)]))}`);
}
export function criarTarefa(payload: TarefaInput): Promise<Tarefa> {
  return request("/tarefas", { method: "POST", body: JSON.stringify(payload) });
}
export function obterPeticao(id: number): Promise<Peticao> { return request(`/peticoes/${id}`); }
export function obterTarefa(id: number): Promise<Tarefa> { return request(`/tarefas/${id}`); }
export type DocumentoVersao = {
  paginas_diagnostico?: { page: number; status: string; ocr: boolean; chars?: number; error?: string }[];
  id: number; sha256: string; mime_type: string; size_bytes: number; paginas: number | null;
  atual: boolean; extracao: string; resumo_status: string; created_at: string;
};
export type DocumentoBiblioteca = {
  id: number; nome: string; tipo: string | null; processo_id: number | null; processo_numero: string | null;
  cliente_nome: string | null; grau: string | null; no_contexto: boolean; versao: DocumentoVersao | null;
};
export type DocumentoRecebido = {
  id: number; nome: string; documento_id: number | null; documento_arquivo_id: number | null; sha256: string; created_at: string;
};
export type DocumentoTrechos = Pagina<{ id: number; pagina: number; texto: string; ocr: boolean }> & {
  resumo: string | null; citations: { pagina?: number; quote?: string; chunk_id?: number }[]; versao: DocumentoVersao;
};
export function listarDocumentos(params: { processo_id?: number; q?: string; limit?: number; offset?: number } = {}): Promise<Pagina<DocumentoBiblioteca>> {
  return request(`/documentos?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)]))}`);
}
export function listarVersoesDocumento(id: number, offset = 0): Promise<Pagina<DocumentoVersao>> {
  return request(`/documentos/${id}/versoes?limit=30&offset=${offset}`);
}
export function listarTrechosDocumento(id: number, version: number, q = "", offset = 0): Promise<DocumentoTrechos> {
  return request(`/documentos/${id}/versoes/${version}/trechos?${new URLSearchParams({ q, offset: String(offset), limit: "20" })}`);
}
export function listarDocumentosTarefa(id: number): Promise<DocumentoRecebido[]> { return request(`/tarefas/${id}/documentos`); }
export function atualizarTarefa(id: number, payload: TarefaPatch): Promise<Tarefa> {
  return request(`/tarefas/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export type ProximoPrazo = {
  data_fatal: string;
  cumprido: boolean;
  descricao: string | null;
  revisao_status?: string;
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
  revisao_status?: string;
};

export function repetirAnalisePrazo(id: number): Promise<{ job_id: number | null }> {
  return request(`/intimacoes/${id}/analisar-prazo`, { method: "POST" });
}

export async function confirmarPrazoIntimacao(intimacaoId: number, payload: {
  data_base: string; dias: number; dias_uteis: boolean; justificativa: string; dias_sem_expediente: string[]; descricao?: string;
}): Promise<Prazo> {
  return request(`/intimacoes/${intimacaoId}/prazo`, { method: "POST", body: JSON.stringify(payload) });
}

/** Dossiê de apoio gerado junto com a minuta. Fica separado de `conteudo` (que
 * carrega só o texto da peça) e serve de contexto para a revisão do advogado. */
export type Dossie = {
  trabalho_id?: number;
  selecao_contexto?: { excerpts_total: number; excerpts_selected: number; excerpts_omitted: number };
  contexto_consolidado?: string;
  analise_providencia?: string;
  alertas?: string[];
  confianca?: number;
  citations?: { documento_id: number; documento_arquivo_id: number; chunk_id: number; pagina: number; quote: string }[];
};

export async function baixarFonteCitada(documentoId: number, versaoId: number): Promise<Blob> {
  const { data } = await supabase.auth.getSession();
  const response = await fetch(`${API_BASE}/documentos/${documentoId}/versoes/${versaoId}/conteudo`, {
    headers: withAuthHeaders({}, data.session?.access_token), cache: "no-store"
  });
  if (!response.ok) throw new Error(`Falha ao abrir fonte: ${response.status}`);
  return response.blob();
}

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
  djen_indisponivel?: boolean;
  djen_erro?: string | null;
  // Intimações antigas capturadas cujo prazo provisório já estaria vencido: são
  // gravadas, mas não geram prazo (evita parede de alarme falso no painel de
  // risco). Opcional porque backend anterior à mudança não envia o campo.
  prazos_historicos?: number;
  /** Publicações devolvidas pelo DJEN na janela (novas ou já conhecidas). */
  publicacoes_encontradas?: number;
  /** UFs em que o número da OAB aparece quando a UF informada não trouxe nada. */
  ufs_sugeridas?: string[];
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
  prazo_dias: number | null;
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
  revisao_status?: string;
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

export type Papel = "administrador" | "advogado" | "assistente";
export type Permissao = "gerir_equipe" | "configurar_escritorio" | "aprovar_minuta" | "decidir_prazo" | "excluir_trabalho" | "excluir_processo" | "excluir_cliente";

export type Usuario = {
  id: number;
  escritorio_id: number;
  nome: string;
  email: string | null;
  oab: string | null;
  oab_uf: string | null;
  papel: Papel;
  ativo: boolean;
  /** Convidado que ainda não entrou no Causor. */
  convite_pendente: boolean;
};

export type ResultadoConvite = "enviado" | "ja_cadastrado" | "manual";

export type Escritorio = {
  id: number;
  nome: string;
  cnpj: string | null;
  timbrado_cabecalho: string | null;
  timbrado_rodape: string | null;
  /** PNG em base64, já normalizado pelo backend. */
  timbrado_logo: string | null;
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
  timbrado_cabecalho: string;
  timbrado_rodape: string;
  /** Base64 de PNG/JPEG; string vazia remove o logo. */
  timbrado_logo: string;
}>;

export type CurrentUser = {
  usuario_id: number;
  escritorio_id: number;
  email: string;
  papel: Papel;
  permissoes: Permissao[];
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
  oab_id: number | null;
  oab: string;
  uf: string;
  purge: boolean;
  removidos: Record<string, number>;
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

// As páginas (Processos, Intimações, Prazos, Petições) montam as listas do lado
// do cliente. Com o default de 100 elas subcontavam vs. o dashboard (que conta no
// servidor) — Processos 195 vs 200, Intimações travava em 100, Prazos em 200.
// Carregamos a base inteira até este teto (alvo ~3k/conta; `le=5000` no backend).
// Acima disso é preciso paginação server-side de verdade.
const LIST_PAGE_LIMIT = 5000;
const AUTH_REFRESH_TIMEOUT_MS = 8000;

let refreshInFlight: { userId: string | undefined; promise: Promise<string | null> } | null = null;
let signOutInFlight: Promise<void> | null = null;

async function expireLocalSession(): Promise<void> {
  if (!signOutInFlight) {
    const attempt = supabase.auth.signOut({ scope: "local" }).then(() => undefined, () => undefined);
    signOutInFlight = attempt;
    void attempt.then(() => { if (signOutInFlight === attempt) signOutInFlight = null; });
  }
  await signOutInFlight;
}

function changedAccount(originalUserId: string | undefined, currentUserId: string | undefined): boolean {
  return originalUserId !== currentUserId;
}

async function recoverRejectedToken(rejectedToken: string | undefined, originalUserId: string | undefined): Promise<string | null> {
  while (refreshInFlight && refreshInFlight.userId !== originalUserId) {
    await refreshInFlight.promise.catch(() => undefined);
  }
  if (!refreshInFlight) {
    let timedOut = false;
    const attempt = (async () => {
      try {
        const session = (await supabase.auth.getSession()).data.session;
        if (timedOut) return null;
        if (changedAccount(originalUserId, session?.user?.id)) throw new Error("Conta alterada durante a solicitação.");
        const current = session?.access_token;
        if (current && current !== rejectedToken) return current;
        const { data, error } = await supabase.auth.refreshSession();
        if (timedOut) return null;
        if (changedAccount(originalUserId, data.session?.user?.id)) throw new Error("Conta alterada durante a solicitação.");
        const refreshed = data.session?.access_token;
        if (error) throw new Error("Não foi possível renovar a sessão. Tente novamente.");
        if (!error && refreshed && refreshed !== rejectedToken) return refreshed;
      } catch (error) {
        if (timedOut) return null;
        if (error instanceof Error && error.message === "Conta alterada durante a solicitação.") throw error;
        throw new Error("Não foi possível renovar a sessão. Tente novamente.");
      }
      // Local scope leaves the user's other devices signed in. The auth event
      // clears AuthProvider, whose protected pages navigate to /login.
      const latestUserId = (await supabase.auth.getSession()).data.session?.user?.id;
      if (timedOut) return null;
      if (changedAccount(originalUserId, latestUserId)) throw new Error("Conta alterada durante a solicitação.");
      await expireLocalSession();
      return null;
    })();
    let timeoutId: ReturnType<typeof setTimeout>;
    const timeout = new Promise<never>((_, reject) => {
      timeoutId = setTimeout(() => {
        timedOut = true;
        reject(new Error("Não foi possível renovar a sessão. Tente novamente."));
      }, AUTH_REFRESH_TIMEOUT_MS);
    });
    const bounded = Promise.race([attempt, timeout]);
    const pending = { userId: originalUserId, promise: bounded };
    refreshInFlight = pending;
    void bounded.then(() => { clearTimeout(timeoutId); if (refreshInFlight === pending) refreshInFlight = null; },
      () => { clearTimeout(timeoutId); if (refreshInFlight === pending) refreshInFlight = null; });
  }
  return refreshInFlight.promise;
}

async function fetchWithAuth(path: string, init: RequestInit, token: string | undefined, json: boolean, userId?: string): Promise<Response> {
  const send = (accessToken: string | undefined) => fetch(`${API_BASE}${path}`, {
    ...init,
    cache: "no-store",
    headers: withAuthHeaders({ ...(json ? { "Content-Type": "application/json" } : {}),
      ...((init.headers as Record<string, string>) ?? {}) }, accessToken)
  });
  let response = await send(token);
  if (response.status === 401) {
    const replacement = await recoverRejectedToken(token, userId);
    if (replacement) {
      const currentUserId = (await supabase.auth.getSession()).data.session?.user?.id;
      if (changedAccount(userId, currentUserId)) throw new Error("Conta alterada durante a solicitação.");
      response = await send(replacement);
    }
    if (response.status === 401 || !replacement) {
      if (replacement) {
        const currentUserId = (await supabase.auth.getSession()).data.session?.user?.id;
        if (changedAccount(userId, currentUserId)) throw new Error("Conta alterada durante a solicitação.");
        await expireLocalSession();
      }
      throw new Error("Sessão expirada. Entre novamente.");
    }
  }
  return response;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { data } = await supabase.auth.getSession();
  const response = await fetchWithAuth(path, init ?? {}, data.session?.access_token, true, data.session?.user?.id);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

/** Short control requests must never leave capture UI waiting indefinitely. */
export async function controlRequest<T>(path: string, init?: RequestInit, timeoutMs = 12000): Promise<T> {
  const controller = new AbortController();
  const timeout = new Promise<never>((_, reject) => {
    const id = setTimeout(() => {
      controller.abort();
      reject(new Error("Tempo de resposta excedido. Verifique a captura novamente."));
    }, timeoutMs);
    controller.signal.addEventListener("abort", () => clearTimeout(id), { once: true });
  });
  const operation = (async () => {
    const { data } = await supabase.auth.getSession();
    const response = await fetchWithAuth(path, { ...init, signal: controller.signal }, data.session?.access_token, true, data.session?.user?.id);
    if (!response.ok) throw new Error(await response.text() || `Falha: ${response.status}`);
    return response.json() as Promise<T>;
  })();
  try {
    return await Promise.race([operation, timeout]);
  } finally {
    controller.abort();
  }
}

/** Authenticated binary/multipart transport; callers never receive a public storage URL. */
export async function resourceRequest(path: string, init?: RequestInit): Promise<Response> {
  const { data } = await supabase.auth.getSession();
  const response = await fetchWithAuth(path, init ?? {}, data.session?.access_token, false, data.session?.user?.id);
  if (!response.ok) throw new Error(await response.text() || `Falha: ${response.status}`);
  return response;
}

async function requestOptional<T>(path: string): Promise<T | undefined> {
  try {
    return await controlRequest<T>(path, undefined, 20000);
  } catch (err) {
    console.warn(`Endpoint opcional indisponível: ${path}`, err);
    return undefined;
  }
}

async function requestList<T>(path: string): Promise<{ data: T[]; failed: boolean }> {
  try {
    return { data: await controlRequest<T[]>(path, undefined, 20000), failed: false };
  } catch (err) {
    console.warn(`Falha ao carregar ${path}`, err);
    return { data: [], failed: true };
  }
}

export type IntimacaoAnalysis = Pick<Intimacao, "id" | "prazo_analise">;

export async function consultarAnalisesPrazo(ids: number[]): Promise<IntimacaoAnalysis[]> {
  const unique = [...new Set(ids)];
  const results: IntimacaoAnalysis[] = [];
  for (let start = 0; start < unique.length; start += 200) {
    const query = new URLSearchParams();
    unique.slice(start, start + 200).forEach(id => query.append("ids", String(id)));
    results.push(...await controlRequest<IntimacaoAnalysis[]>(`/intimacoes/analise-status?${query}`));
  }
  return results;
}

export async function loadDashboard(): Promise<DashboardData> {
  // Cada lista falha de forma independente: um 500/timeout isolado em UM
  // endpoint nao deve zerar os outros tres (era o que Promise.all fazia antes
  // - uma falha rejeitava tudo e a tela inteira parecia vazia).
  const [intimacoes, processos, prazos, peticoes] = await Promise.all([
    requestList<Intimacao>(`/intimacoes?limit=${LIST_PAGE_LIMIT}`),
    requestList<Processo>(`/processos?limit=${LIST_PAGE_LIMIT}`),
    requestList<Prazo>(`/prazos?limit=${LIST_PAGE_LIMIT}`),
    requestList<Peticao>(`/peticoes?limit=${LIST_PAGE_LIMIT}`)
  ]);
  const [operational, reviewQueue, processosResumo] = await Promise.all([
    requestOptional<OperationalDashboard>("/dashboard/operational"),
    requestOptional<ReviewQueueItem[]>(`/review/queue?limit=${LIST_PAGE_LIMIT}`),
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
  return controlRequest<OabMonitorada[]>("/capturas/oab");
}

export function iniciarCapturaOab(oab: string, uf: string, requestId: string): Promise<JobExecucao> {
  return controlRequest<JobExecucao>("/jobs/capture/oab", {
    method: "POST", body: JSON.stringify({ oab, uf, request_id: requestId })
  });
}

export function consultarCapturaOab(jobId: number): Promise<JobExecucao> {
  return controlRequest<JobExecucao>(`/jobs/${jobId}`);
}

export function listarCapturasOab(): Promise<JobExecucao[]> {
  return controlRequest<JobExecucao[]>("/jobs?tipo=captura_oab&limit=200");
}

export async function listarUsuarios(escritorioId?: number): Promise<Usuario[]> {
  const qs = escritorioId != null ? `?escritorio_id=${escritorioId}` : "";
  return request<Usuario[]>(`/usuarios${qs}`);
}

export function convidarMembro(payload: { nome: string; email: string; papel: Papel }): Promise<{ membro: Usuario; convite: ResultadoConvite }> {
  return request("/equipe/convites", { method: "POST", body: JSON.stringify(payload) });
}

export function reenviarConvite(usuarioId: number): Promise<{ membro: Usuario; convite: ResultadoConvite }> {
  return request(`/equipe/${usuarioId}/convite`, { method: "POST" });
}

export function alterarMembro(usuarioId: number, patch: { papel?: Papel; ativo?: boolean }): Promise<Usuario> {
  return request(`/equipe/${usuarioId}`, { method: "PATCH", body: JSON.stringify(patch) });
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

export async function baixarPeticaoPdf(peticaoId: number): Promise<Blob> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const response = await fetch(`${API_BASE}/peticoes/${peticaoId}/pdf`, {
    headers: withAuthHeaders({}, token),
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`Falha ao baixar PDF: ${response.status}`);
  }
  return response.blob();
}

let currentUserCache: CurrentUser | null = null;

export async function carregarUsuarioAtual(): Promise<CurrentUser> {
  if (currentUserCache != null) return currentUserCache;
  currentUserCache = await request<CurrentUser>("/me");
  return currentUserCache;
}

/** Troca de conta na mesma aba não pode herdar o papel da anterior. */
export function esquecerUsuarioAtual(): void {
  currentUserCache = null;
}

export async function resolverUsuarioAtual(): Promise<number> {
  return (await carregarUsuarioAtual()).usuario_id;
}

export async function resolverEscritorioAtual(): Promise<number> {
  return (await carregarUsuarioAtual()).escritorio_id;
}

export type CapturaAutos = {
  id: number;
  processo_instancia_id: number;
  generation: number;
  status: string;
  expected_count: number;
  captured_count: number;
  missing_count: number;
  error_code: string | null;
  started_at: string | null;
  completed_at: string | null;
  fonte?: string;
};

export type AutosInstanciaStatus = {
  processo_instancia_id: number;
  sistema: string;
  tribunal: string;
  grau: string;
  captura: CapturaAutos | null;
};

export type AutosStatus = {
  processo_id: number;
  instancias: AutosInstanciaStatus[];
  contexto?: {
    ready: boolean;
    missing: string[];
    documents_total?: number;
    documents_extracted?: number;
    documents_summarized?: number;
  };
};

export async function declararGrauNaoAplicavel(processoId: number, grau: string, justificativa: string) {
  return request(`/processos/${processoId}/autos/nao-aplicavel`, {
    method: "POST", body: JSON.stringify({ grau, justificativa })
  });
}

export async function reprocessarAutos(processoId: number) {
  return request(`/processos/${processoId}/autos/reprocessar`, { method: "POST" });
}

export async function statusAutos(processoId: number): Promise<AutosStatus> {
  return request<AutosStatus>(`/processos/${processoId}/autos/status`);
}

/** Envia os autos que o próprio advogado baixou no tribunal.
 *
 * Único caminho de captura sem gate externo: não exige pareamento, credencial
 * nem conector. Vai por `fetch` direto porque `request` fixa
 * `Content-Type: application/json` — em multipart quem define o cabeçalho (com
 * o boundary) tem de ser o browser. */
export async function enviarAutos(
  processoId: number,
  arquivos: File[],
  grau: string = "1",
  complemento?: { tarefa?: Pick<Tarefa, "id" | "versao">; perfilResumo?: "padrao" | "aprofundada" }
): Promise<CapturaAutos> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const form = new FormData();
  form.append("grau", grau);
  form.append("perfil_resumo", complemento?.perfilResumo || "padrao");
  if (complemento) {
    form.append("complementar", "true");
    if (complemento.tarefa) {
      form.append("tarefa_id", String(complemento.tarefa.id));
      form.append("tarefa_versao", String(complemento.tarefa.versao));
    }
  }
  for (const arquivo of arquivos) form.append("arquivos", arquivo);

  const response = await fetch(`${API_BASE}/processos/${processoId}/autos/upload`, {
    method: "POST",
    headers: withAuthHeaders({}, token),
    body: form,
    cache: "no-store"
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return (await response.json()) as CapturaAutos;
}

export async function criarOverrideContexto(
  processoId: number,
  action: "draft" | "file",
  justification: string
): Promise<{ id: number; action: string; expires_at: string }> {
  return request(`/processos/${processoId}/contexto/override`, {
    method: "POST",
    body: JSON.stringify({ action, justification })
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
  processoId?: number,
  trabalhoId?: number
): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ messages, processo_id: processoId ?? null, trabalho_id: trabalhoId ?? null })
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

export function removerDadosOab(oab: string, uf: string): Promise<OabRemovalResult> {
  return request("/capturas/oab/remover-dados", {
    method: "POST", body: JSON.stringify({ oab, uf })
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
