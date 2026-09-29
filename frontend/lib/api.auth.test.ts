import { afterEach, expect, it, vi } from "vitest";

const getSession = vi.fn();
const refreshSession = vi.fn();
const signOut = vi.fn();
vi.mock("./supabase", () => ({ supabase: { auth: { getSession, refreshSession, signOut } } }));

function response(status: number) {
  return { status, ok: status >= 200 && status < 300, json: async () => ({ ok: true }), text: async () => "" } as Response;
}

afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); vi.resetModules(); });

it("shares one refresh across simultaneous 401 responses and retries once", async () => {
  getSession.mockResolvedValue({ data: { session: { access_token: "old", user: { id: "a" } } } });
  refreshSession.mockResolvedValue({ data: { session: { access_token: "new", user: { id: "a" } } }, error: null });
  const fetcher = vi.fn(async (_url, init: RequestInit) => response((init.headers as Record<string, string>).Authorization === "Bearer old" ? 401 : 200));
  vi.stubGlobal("fetch", fetcher);
  const { request } = await import("./api");
  await Promise.all([request("/one"), request("/two")]);
  expect(refreshSession).toHaveBeenCalledTimes(1);
  expect(fetcher).toHaveBeenCalledTimes(4);
  expect(signOut).not.toHaveBeenCalled();
});

it("expires locally after a second 401 without another refresh", async () => {
  getSession.mockResolvedValue({ data: { session: { access_token: "old", user: { id: "a" } } } });
  refreshSession.mockResolvedValue({ data: { session: { access_token: "new", user: { id: "a" } } }, error: null });
  signOut.mockResolvedValue({ error: null });
  const fetcher = vi.fn(async () => response(401));
  vi.stubGlobal("fetch", fetcher);
  const { request } = await import("./api");
  await expect(request("/one", { method: "POST" })).rejects.toThrow("Sessão expirada");
  expect(refreshSession).toHaveBeenCalledTimes(1);
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(signOut).toHaveBeenCalledWith({ scope: "local" });
});

it("does not retry an old account's mutation with a newly signed-in account", async () => {
  let session = { access_token: "old", user: { id: "a" } };
  getSession.mockImplementation(async () => ({ data: { session } }));
  refreshSession.mockImplementation(async () => {
    session = { access_token: "other", user: { id: "b" } };
    return { data: { session }, error: null };
  });
  const fetcher = vi.fn(async () => response(401));
  vi.stubGlobal("fetch", fetcher);
  const { request } = await import("./api");
  await expect(request("/mutation", { method: "POST" })).rejects.toThrow("Conta alterada");
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(signOut).not.toHaveBeenCalled();
});

it("does not replay a request started without a session after a user signs in", async () => {
  let session: { access_token: string; user: { id: string } } | null = null;
  getSession.mockImplementation(async () => ({ data: { session } }));
  const fetcher = vi.fn(async () => { session = { access_token: "new", user: { id: "b" } }; return response(401); });
  vi.stubGlobal("fetch", fetcher);
  const { request } = await import("./api");
  await expect(request("/mutation", { method: "POST" })).rejects.toThrow("Conta alterada");
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(refreshSession).not.toHaveBeenCalled();
  expect(signOut).not.toHaveBeenCalled();
});

it("does not refresh or replay a request after its user signs out", async () => {
  let session: { access_token: string; user: { id: string } } | null = { access_token: "old", user: { id: "a" } };
  getSession.mockImplementation(async () => ({ data: { session } }));
  const fetcher = vi.fn(async () => { session = null; return response(401); });
  vi.stubGlobal("fetch", fetcher);
  const { request } = await import("./api");
  await expect(request("/mutation", { method: "POST" })).rejects.toThrow("Conta alterada");
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(refreshSession).not.toHaveBeenCalled();
  expect(signOut).not.toHaveBeenCalled();
});

it("keeps the capture control request bounded while token refresh hangs", async () => {
  getSession.mockResolvedValue({ data: { session: { access_token: "old", user: { id: "a" } } } });
  refreshSession.mockImplementation(() => new Promise(() => {}));
  vi.stubGlobal("fetch", vi.fn(async () => response(401)));
  vi.useFakeTimers();
  try {
    const { controlRequest } = await import("./api");
    const rejection = expect(controlRequest("/capture/oab", undefined, 100)).rejects.toThrow("Tempo de resposta excedido");
    await vi.advanceTimersByTimeAsync(100);
    await rejection;
  } finally { vi.useRealTimers(); }
});

it("releases a hung shared refresh and lets a later request recover without signing out", async () => {
  getSession.mockResolvedValue({ data: { session: { access_token: "old", user: { id: "a" } } } });
  refreshSession.mockImplementationOnce(() => new Promise(() => {}))
    .mockResolvedValueOnce({ data: { session: { access_token: "new", user: { id: "a" } } }, error: null });
  const fetcher = vi.fn(async (_url, init: RequestInit) =>
    response((init.headers as Record<string, string>).Authorization === "Bearer old" ? 401 : 200));
  vi.stubGlobal("fetch", fetcher);
  vi.useFakeTimers();
  try {
    const { request } = await import("./api");
    const first = expect(request("/first", { method: "POST" })).rejects.toThrow("Não foi possível renovar");
    await vi.advanceTimersByTimeAsync(8000);
    await first;
    expect(signOut).not.toHaveBeenCalled();
    expect(await request("/second", { method: "POST" })).toEqual({ ok: true });
    expect(refreshSession).toHaveBeenCalledTimes(2);
    expect(fetcher).toHaveBeenCalledTimes(3);
    expect(signOut).not.toHaveBeenCalled();
  } finally { vi.useRealTimers(); }
});
