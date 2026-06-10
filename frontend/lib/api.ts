export type Intimacao = {
  id: number;
  processo_id: number | null;
  fonte: string;
  numero_processo: string | null;
  tribunal: string | null;
  tipo_comunicacao: string | null;
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

export type DashboardData = {
  intimacoes: Intimacao[];
  processos: Processo[];
  prazos: Prazo[];
  peticoes: Peticao[];
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

export async function loadDashboard(): Promise<DashboardData> {
  const [intimacoes, processos, prazos, peticoes] = await Promise.all([
    request<Intimacao[]>("/intimacoes"),
    request<Processo[]>("/processos"),
    request<Prazo[]>("/prazos"),
    request<Peticao[]>("/peticoes")
  ]);
  return { intimacoes, processos, prazos, peticoes };
}

export async function gerarMinuta(intimacaoId: number): Promise<void> {
  await request(`/intimacoes/${intimacaoId}/draft`, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export async function aprovarPeticao(peticaoId: number): Promise<void> {
  await request(`/peticoes/${peticaoId}/approve`, {
    method: "POST",
    body: JSON.stringify({ usuario_id: 1 })
  });
}

export async function protocolarPeticao(peticaoId: number): Promise<void> {
  await request(`/peticoes/${peticaoId}/protocolar`, { method: "POST" });
}
