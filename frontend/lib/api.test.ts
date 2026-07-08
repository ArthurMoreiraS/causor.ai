import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getSession = vi.fn();

vi.mock("./supabase", () => ({
  supabase: {
    auth: { getSession }
  }
}));

type MockResponse = {
  status?: number;
  body?: unknown;
};

function mockFetch(responses: Record<string, MockResponse>) {
  return vi.fn(async (input: string | URL, init?: RequestInit) => {
    const url = String(input);
    const path = new URL(url).pathname;
    const response = responses[`${init?.method ?? "GET"} ${path}`];
    if (!response) {
      throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${path}`);
    }
    const status = response.status ?? 200;
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => response.body,
      text: async () =>
        typeof response.body === "string" ? response.body : JSON.stringify(response.body)
    } as Response;
  });
}

describe("API client critical workflows", () => {
  beforeEach(() => {
    getSession.mockResolvedValue({
      data: { session: { access_token: "test-token" } }
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    vi.resetModules();
  });

  it("loads core dashboard data and sends the bearer token", async () => {
    const fetchMock = mockFetch({
      "GET /intimacoes": { body: [] },
      "GET /processos": { body: [] },
      "GET /prazos": { body: [] },
      "GET /peticoes": { body: [] },
      "GET /dashboard/operational": { body: { metrics: [], workflow: [], connectors: [], audit_signals: [] } },
      "GET /review/queue": { body: [] },
      "GET /processos/resumo": { body: { total: 0, items: [] } }
    });
    vi.stubGlobal("fetch", fetchMock);
    const { loadDashboard } = await import("./api");

    const result = await loadDashboard();

    expect(result.backendOffline).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(7);
    for (const [, init] of fetchMock.mock.calls) {
      expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
    }
  });

  it("requests every core list well above the 100 default so all pages match the dashboard counts", async () => {
    // Deriving pages from lists capped at 100 under-reported (Processos 195 vs
    // dashboard 200; Intimações travava em 100; Prazos em 200). Every list loads
    // the full population (limit=5000) so page counts match the server counts.
    const fetchMock = mockFetch({
      "GET /intimacoes": { body: [] },
      "GET /processos": { body: [] },
      "GET /prazos": { body: [] },
      "GET /peticoes": { body: [] },
      "GET /dashboard/operational": { body: { metrics: [], workflow: [], connectors: [], audit_signals: [] } },
      "GET /review/queue": { body: [] },
      "GET /processos/resumo": { body: { total: 0, items: [] } }
    });
    vi.stubGlobal("fetch", fetchMock);
    const { loadDashboard } = await import("./api");

    await loadDashboard();

    const limitOf = (path: string) => {
      const call = fetchMock.mock.calls.find(([url]) => new URL(String(url)).pathname === path);
      expect(call).toBeDefined();
      return new URL(String(call![0])).searchParams.get("limit");
    };
    for (const path of ["/intimacoes", "/processos", "/prazos", "/peticoes", "/review/queue"]) {
      expect(limitOf(path)).toBe("5000");
    }
  });

  it("loads the enriched /processos/resumo so the page can match the dashboard count", async () => {
    const fetchMock = mockFetch({
      "GET /intimacoes": { body: [] },
      "GET /processos": { body: [] },
      "GET /prazos": { body: [] },
      "GET /peticoes": { body: [] },
      "GET /dashboard/operational": { body: { metrics: [], workflow: [], connectors: [], audit_signals: [] } },
      "GET /review/queue": { body: [] },
      "GET /processos/resumo": { body: { total: 2, items: [{ id: 1 }, { id: 2 }] } }
    });
    vi.stubGlobal("fetch", fetchMock);
    const { loadDashboard } = await import("./api");

    const result = await loadDashboard();

    expect(result.processosResumo?.total).toBe(2);
    expect(result.processosResumo?.items).toHaveLength(2);
  });

  it("normalizes a trailing slash in NEXT_PUBLIC_API_BASE before requesting core endpoints", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://localhost:8000/");
    const fetchMock = mockFetch({
      "GET /intimacoes": { body: [] },
      "GET /processos": { body: [] },
      "GET /prazos": { body: [] },
      "GET /peticoes": { body: [] },
      "GET /dashboard/operational": { body: { metrics: [], workflow: [], connectors: [], audit_signals: [] } },
      "GET /review/queue": { body: [] },
      "GET /processos/resumo": { body: { total: 0, items: [] } }
    });
    vi.stubGlobal("fetch", fetchMock);
    const { loadDashboard } = await import("./api");

    await loadDashboard();

    expect(fetchMock.mock.calls.map(([url]) => new URL(String(url)).pathname)).toEqual([
      "/intimacoes",
      "/processos",
      "/prazos",
      "/peticoes",
      "/dashboard/operational",
      "/review/queue",
      "/processos/resumo"
    ]);
  });

  it("registers the monitored OAB before running the immediate capture", async () => {
    const fetchMock = mockFetch({
      "POST /capturas/oab": { body: { id: 1, oab: "12345", uf: "SP" } },
      "POST /capture/oab": {
        body: { intimacoes_novas: 2, processos_enriquecidos: 1, prazos_registrados: 1 }
      }
    });
    vi.stubGlobal("fetch", fetchMock);
    const { rodarCapturaOab } = await import("./api");

    const result = await rodarCapturaOab("12345", "SP");

    expect(result.intimacoes_novas).toBe(2);
    expect(fetchMock.mock.calls.map(([url]) => new URL(String(url)).pathname)).toEqual([
      "/capturas/oab",
      "/capture/oab"
    ]);
  });

  it("resolves the current user and includes it when reviewing a deadline", async () => {
    const prazo = {
      id: 8,
      processo_id: 3,
      intimacao_id: 4,
      descricao: "Manifestar",
      data_inicio: "2026-06-25",
      dias: 10,
      dias_uteis: true,
      data_fatal: "2026-07-09",
      cumprido: false
    };
    const fetchMock = mockFetch({
      "GET /me": { body: { usuario_id: 7, escritorio_id: 2, email: "adv@example.com" } },
      "PATCH /prazos/8": { body: prazo }
    });
    vi.stubGlobal("fetch", fetchMock);
    const { revisarPrazo } = await import("./api");

    await revisarPrazo(8, { dias: 10 });

    const patch = fetchMock.mock.calls[1][1];
    expect(JSON.parse(String(patch?.body))).toEqual({ usuario_id: 7, dias: 10 });
  });

  it("keeps approval and assisted filing as separate requests", async () => {
    const fetchMock = mockFetch({
      "GET /me": { body: { usuario_id: 7, escritorio_id: 2, email: "adv@example.com" } },
      "POST /peticoes/11/approve": { body: {} },
      "POST /peticoes/11/protocolar/async": {
        body: { id: 21, tipo: "protocolo_peticao", status: "completed" }
      }
    });
    vi.stubGlobal("fetch", fetchMock);
    const { aprovarPeticao, protocolarPeticaoAsync } = await import("./api");

    await aprovarPeticao(11);
    const job = await protocolarPeticaoAsync(11, 5);

    expect(job.id).toBe(21);
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({ usuario_id: 7 });
    expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toEqual({ credencial_id: 5 });
  });

  it("flags the dashboard offline only when every core list fails together", async () => {
    const fetchMock = mockFetch({
      "GET /intimacoes": { status: 503, body: "temporarily unavailable" },
      "GET /processos": { status: 503, body: "temporarily unavailable" },
      "GET /prazos": { status: 503, body: "temporarily unavailable" },
      "GET /peticoes": { status: 503, body: "temporarily unavailable" }
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const { loadDashboard } = await import("./api");

    const result = await loadDashboard();

    expect(result).toMatchObject({
      intimacoes: [],
      processos: [],
      prazos: [],
      peticoes: [],
      backendOffline: true
    });
  });

  it("keeps the dashboard online when a single core list fails in isolation", async () => {
    const fetchMock = mockFetch({
      "GET /intimacoes": { status: 503, body: "temporarily unavailable" },
      "GET /processos": { body: [{ id: 1 }] },
      "GET /prazos": { body: [] },
      "GET /peticoes": { body: [] },
      "GET /dashboard/operational": { body: { metrics: [], workflow: [], connectors: [], audit_signals: [] } },
      "GET /review/queue": { body: [] }
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const { loadDashboard } = await import("./api");

    const result = await loadDashboard();

    expect(result.backendOffline).toBe(false);
    expect(result.intimacoes).toEqual([]);
    expect(result.processos).toEqual([{ id: 1 }]);
  });
});
