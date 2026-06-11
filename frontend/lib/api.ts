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
  status: "rascunho" | "aprovada" | "protocolada" | string;
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

export type DashboardData = {
  intimacoes: Intimacao[];
  processos: Processo[];
  prazos: Prazo[];
  peticoes: Peticao[];
  reviewQueue?: ReviewQueueItem[];
  operational?: OperationalDashboard;
  demoMode?: boolean;
  backendOffline?: boolean;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const today = new Date();
const isoFromToday = (offsetDays: number) => {
  const value = new Date(today);
  value.setDate(value.getDate() + offsetDays);
  return value.toISOString().slice(0, 10);
};

const demoDashboard: DashboardData = {
  demoMode: true,
  processos: [
    {
      id: 1,
      numero: "1001842-88.2025.8.26.0100",
      classe: "Procedimento Comum Cível",
      tribunal: "TJSP",
      orgao_julgador: "12a Vara Civel",
      sistema: "e-SAJ"
    },
    {
      id: 2,
      numero: "0007341-21.2025.5.02.0031",
      classe: "Reclamação Trabalhista",
      tribunal: "TRT2",
      orgao_julgador: "31a Vara do Trabalho",
      sistema: "PJe"
    },
    {
      id: 3,
      numero: "5012389-44.2025.4.03.6100",
      classe: "Mandado de Seguranca",
      tribunal: "TRF3",
      orgao_julgador: "6a Vara Federal",
      sistema: "PJe"
    }
  ],
  intimacoes: [
    {
      id: 101,
      processo_id: 1,
      fonte: "DJEN",
      numero_processo: "1001842-88.2025.8.26.0100",
      tribunal: "TJSP",
      tipo_comunicacao: "Intimação para manifestação",
      teor: "A parte autora fica intimada para se manifestar sobre os documentos juntados.",
      data_disponibilizacao: isoFromToday(-1),
      data_publicacao: isoFromToday(0)
    },
    {
      id: 102,
      processo_id: 2,
      fonte: "DJEN",
      numero_processo: "0007341-21.2025.5.02.0031",
      tribunal: "TRT2",
      tipo_comunicacao: "Intimação para contestar",
      teor: "Fica a parte reclamada intimada para apresentar contestacao.",
      data_disponibilizacao: isoFromToday(-4),
      data_publicacao: isoFromToday(-3)
    },
    {
      id: 103,
      processo_id: 3,
      fonte: "DJEN",
      numero_processo: "5012389-44.2025.4.03.6100",
      tribunal: "TRF3",
      tipo_comunicacao: "Intimação de decisão liminar",
      teor: "Fica a autoridade coatora intimada da decisao liminar.",
      data_disponibilizacao: isoFromToday(-7),
      data_publicacao: isoFromToday(-6)
    }
  ],
  prazos: [
    {
      id: 201,
      processo_id: 1,
      intimacao_id: 101,
      descricao: "Manifestação sobre documentos",
      data_inicio: isoFromToday(0),
      dias: 15,
      dias_uteis: true,
      data_fatal: isoFromToday(12),
      cumprido: false
    },
    {
      id: 202,
      processo_id: 2,
      intimacao_id: 102,
      descricao: "Contestação trabalhista",
      data_inicio: isoFromToday(-3),
      dias: 15,
      dias_uteis: true,
      data_fatal: isoFromToday(2),
      cumprido: false
    },
    {
      id: 203,
      processo_id: 3,
      intimacao_id: 103,
      descricao: "Agravo / pedido de reconsideração",
      data_inicio: isoFromToday(-6),
      dias: 5,
      dias_uteis: true,
      data_fatal: isoFromToday(-1),
      cumprido: false
    }
  ],
  peticoes: [
    {
      id: 301,
      processo_id: 2,
      prazo_id: 202,
      tipo: "Contestação",
      conteudo:
        "Minuta estruturada com síntese dos fatos, preliminares aplicáveis e pedidos. Aguardando revisão do advogado responsável antes do protocolo.",
      status: "rascunho",
      aprovada_por: null,
      protocolada_em: null
    },
    {
      id: 302,
      processo_id: 1,
      prazo_id: 201,
      tipo: "Manifestação",
      conteudo:
        "Manifestação preparada a partir da intimação capturada no DJEN e dos metadados do processo no SOR.",
      status: "aprovada",
      aprovada_por: 1,
      protocolada_em: null
    }
  ],
  operational: {
    metrics: [
      { key: "processos", label: "Processos monitorados", value: 3 },
      { key: "intimacoes", label: "Intimações capturadas", value: 3 },
      { key: "prazos", label: "Prazos pendentes", value: 3 },
      { key: "risco", label: "Alto risco", value: 2 }
    ],
    workflow: [
      { key: "capture", label: "Captura", detail: "DJEN + DataJud", status: "live" },
      { key: "deadline", label: "Prazo", detail: "Motor determinístico", status: "live" },
      { key: "draft", label: "Minuta", detail: "Claude + templates", status: "review" },
      { key: "approval", label: "Aprovação", detail: "Gate humano OAB", status: "review" },
      { key: "filing", label: "Protocolo", detail: "Conector PJe/e-SAJ", status: "planned" }
    ],
    connectors: [
      { key: "djen", name: "DJEN", detail: "captura oficial", status: "online" },
      { key: "datajud", name: "DataJud", detail: "metadados e andamentos", status: "online" },
      { key: "pje", name: "PJe", detail: "protocolo assistido", status: "pilot" },
      { key: "esaj", name: "e-SAJ", detail: "próximo conector", status: "planned" }
    ],
    audit_signals: [
      {
        key: "gate",
        title: "Gate humano ativo",
        detail: "Protocolo exige aprovação do advogado."
      },
      {
        key: "secrets",
        title: "Segredos fora do prompt",
        detail: "Certificados e senhas pertencem ao vault."
      },
      {
        key: "audit",
        title: "Log operacional",
        detail: "Cada passo do agente fica rastreável."
      }
    ]
  }
};

demoDashboard.reviewQueue = demoDashboard.intimacoes.map((intimacao) => {
  const prazo = demoDashboard.prazos.find((item) => item.intimacao_id === intimacao.id) ?? null;
  const processo = demoDashboard.processos.find((item) => item.id === intimacao.processo_id) ?? null;
  const peticao =
    demoDashboard.peticoes.find((item) => item.prazo_id === prazo?.id) ??
    demoDashboard.peticoes.find((item) => item.processo_id === processo?.id) ??
    null;
  const dias = prazo
    ? Math.ceil((new Date(prazo.data_fatal).getTime() - today.getTime()) / 86_400_000)
    : null;
  return {
    intimacao,
    processo,
    prazo,
    peticao,
    status: prazo?.cumprido
      ? "cumprido"
      : peticao?.status === "aprovada"
        ? "pronta_para_protocolo"
        : peticao?.status === "rascunho"
          ? "minuta_em_revisao"
          : prazo
            ? "prazo_calculado"
            : "capturada",
    risco: prazo?.cumprido
      ? "cumprido"
      : dias === null
        ? "sem_prazo"
        : dias < 0
          ? "vencido"
          : dias <= 3
            ? "alto"
            : "baixo",
    dias_para_vencer: dias
  };
});

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

export async function loadDashboard(): Promise<DashboardData> {
  try {
    const [intimacoes, processos, prazos, peticoes, operational, reviewQueue] = await Promise.all([
      request<Intimacao[]>("/intimacoes"),
      request<Processo[]>("/processos"),
      request<Prazo[]>("/prazos"),
      request<Peticao[]>("/peticoes"),
      request<OperationalDashboard>("/dashboard/operational"),
      request<ReviewQueueItem[]>("/review/queue")
    ]);
    // Backend reachable: reflect its real state (even when empty). Never inject
    // demo rows over a live backend — empty is a real, actionable state.
    return {
      intimacoes,
      processos,
      prazos,
      peticoes,
      operational,
      reviewQueue,
      demoMode: false
    };
  } catch {
    // Backend unreachable: show demo data but flag it so the UI can warn the
    // user and disable actions instead of silently no-oping every button.
    return { ...demoDashboard, backendOffline: true };
  }
}

export async function gerarMinuta(intimacaoId: number): Promise<Classificacao | null> {
  if (demoDashboard.intimacoes.some((item) => item.id === intimacaoId)) return null;
  const resp = await request<{ classificacao: Classificacao }>(
    `/intimacoes/${intimacaoId}/draft`,
    { method: "POST", body: JSON.stringify({}) }
  );
  return resp.classificacao;
}

export async function aprovarPeticao(peticaoId: number): Promise<void> {
  if (demoDashboard.peticoes.some((item) => item.id === peticaoId)) return;
  await request(`/peticoes/${peticaoId}/approve`, {
    method: "POST",
    body: JSON.stringify({ usuario_id: 1 })
  });
}

export async function protocolarPeticao(peticaoId: number): Promise<void> {
  if (demoDashboard.peticoes.some((item) => item.id === peticaoId)) return;
  await request(`/peticoes/${peticaoId}/protocolar`, { method: "POST" });
}

export async function rodarCapturaDemo(): Promise<CaptureResult> {
  return request<CaptureResult>("/capture/demo", {
    method: "POST",
    body: JSON.stringify({})
  });
}

export async function cumprirPrazo(prazoId: number): Promise<void> {
  if (demoDashboard.prazos.some((item) => item.id === prazoId)) return;
  await request(`/prazos/${prazoId}/cumprir`, {
    method: "POST",
    body: JSON.stringify({ usuario_id: 1 })
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
  return request<Prazo>(`/prazos/${prazoId}`, {
    method: "PATCH",
    body: JSON.stringify({ usuario_id: 1, ...patch })
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
