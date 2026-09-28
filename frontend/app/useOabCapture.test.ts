// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  listarCapturasOab: vi.fn(), iniciarCapturaOab: vi.fn(), consultarCapturaOab: vi.fn()
}));
vi.mock("@/lib/api", () => api);

import { useOabCapture } from "./useOabCapture";
import { captureFailureMessage } from "@/lib/capture-outcome";
import { captureProgress, captureResultFromJob } from "@/lib/oab-capture";

const job = (status: string, result: Record<string, unknown> | null = null) => ({
  id: 42, tipo: "captura_oab", status, entidade: "escritorio", entidade_id: 1,
  payload: { oab: "249340", uf: "SP" }, resultado: result, erro: null,
  created_at: "2026-09-27T12:00:00Z", updated_at: "2026-09-27T12:00:00Z"
});

describe("OAB capture tracking", () => {
  beforeEach(() => { sessionStorage.clear(); api.listarCapturasOab.mockResolvedValue([]); });
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

  it("enqueues once, shows confirmed progress and reports a zero-result completion", async () => {
    api.iniciarCapturaOab.mockResolvedValue(job("queued"));
    api.consultarCapturaOab.mockResolvedValue(job("completed", { intimacoes_novas: 0, prazos_registrados: 0 }));
    const terminal = vi.fn();
    const { result } = renderHook(() => useOabCapture("account-1", vi.fn(), terminal));
    await waitFor(() => expect(api.listarCapturasOab).toHaveBeenCalled());
    await act(async () => { await result.current.submit("249340", "SP"); });
    expect(result.current.phase).toBe("queued");
    expect(result.current.job?.id).toBe(42);
    await act(async () => { await result.current.check(); });
    expect(result.current.phase).toBe("completed");
    expect(terminal).toHaveBeenCalledTimes(1);
    expect(api.iniciarCapturaOab).toHaveBeenCalledTimes(1);
  });

  it("recovers an active job after unmount without announcing historical completion", async () => {
    api.listarCapturasOab.mockResolvedValue([job("running", { windows_done: 2, windows_total: 5 })]);
    const terminal = vi.fn();
    const first = renderHook(() => useOabCapture("account-1", vi.fn(), terminal));
    await waitFor(() => expect(first.result.current.phase).toBe("running"));
    first.unmount();
    const second = renderHook(() => useOabCapture("account-1", vi.fn(), terminal));
    await waitFor(() => expect(second.result.current.phase).toBe("running"));
    expect(second.result.current.job?.resultado?.windows_done).toBe(2);
    expect(api.iniciarCapturaOab).not.toHaveBeenCalled();
    expect(terminal).not.toHaveBeenCalled();
  });

  it("reconciles a lost POST response by request key after the job has finished", async () => {
    api.iniciarCapturaOab.mockRejectedValueOnce(new Error("network"));
    const { result } = renderHook(() => useOabCapture("account-1", vi.fn(), vi.fn()));
    await waitFor(() => expect(api.listarCapturasOab).toHaveBeenCalled());
    await act(async () => { await result.current.submit("249340", "SP"); });
    expect(result.current.phase).toBe("lost");
    const attempt = JSON.parse(sessionStorage.getItem("causor:capture-attempt:account-1")!);
    api.listarCapturasOab.mockResolvedValue([{
      ...job("completed", { intimacoes_novas: 1 }), payload: { ...job("completed").payload, request_id: attempt.id }
    }]);
    await act(async () => { await result.current.submit("249340", "SP"); });
    expect(result.current.phase).toBe("completed");
    expect(api.iniciarCapturaOab).toHaveBeenCalledTimes(1);
  });

  it("shows confirmed partial progress and DJEN 403 as failure", async () => {
    const failed = { ...job("failed", { intimacoes_novas: 2, windows_done: 1, windows_total: 3,
      djen_indisponivel: true, djen_erro: "DJEN HTTP 403" }), erro: "DJEN HTTP 403" };
    api.listarCapturasOab.mockResolvedValue([failed]);
    const { result } = renderHook(() => useOabCapture("account-1", vi.fn(), vi.fn()));
    await waitFor(() => expect(result.current.phase).toBe("failed"));
    expect(captureProgress(failed)).toBe("1 de 3 períodos consultados");
    expect(captureFailureMessage(captureResultFromJob(failed))).toContain("2 intimação(ões) foram salvas parcialmente");
  });

  it("releases a lost polling state and can check the same job again", async () => {
    api.listarCapturasOab.mockResolvedValue([job("running")]);
    api.consultarCapturaOab.mockRejectedValueOnce(new Error("rede indisponível"))
      .mockResolvedValueOnce(job("completed", { intimacoes_novas: 1 }));
    const terminal = vi.fn();
    const { result } = renderHook(() => useOabCapture("account-1", vi.fn(), terminal));
    await waitFor(() => expect(result.current.phase).toBe("running"));
    await act(async () => { await result.current.check(); });
    expect(result.current.phase).toBe("lost");
    expect(result.current.job?.id).toBe(42);
    await act(async () => { await result.current.check(); });
    expect(result.current.phase).toBe("completed");
    expect(terminal).toHaveBeenCalledTimes(1);
  });

  it("ignores a response from the previous account", async () => {
    let resolveOld!: (value: ReturnType<typeof job>[]) => void;
    api.listarCapturasOab.mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; }))
      .mockResolvedValue([]);
    const terminal = vi.fn();
    const { result, rerender } = renderHook(({ account }) => useOabCapture(account, vi.fn(), terminal),
      { initialProps: { account: "account-1" } });
    await waitFor(() => expect(api.listarCapturasOab).toHaveBeenCalledTimes(1));
    rerender({ account: "account-2" });
    await act(async () => { resolveOld([job("completed", { intimacoes_novas: 99 })]); });
    await waitFor(() => expect(api.listarCapturasOab).toHaveBeenCalledTimes(2));
    expect(result.current.job).toBeNull();
    expect(terminal).not.toHaveBeenCalled();
  });

  it("reconciles a pending alias before an unrelated active job", async () => {
    sessionStorage.setItem("causor:capture-attempt:account-1", JSON.stringify({ oab: "249340", uf: "SP", id: "alias-B" }));
    const other = { ...job("running"), id: 7, payload: { oab: "777", uf: "RJ" } };
    const matching = { ...job("completed", { intimacoes_novas: 3 }),
      payload: { oab: "249340", uf: "SP", request_id: "alias-A", request_ids: ["alias-B"] } };
    api.listarCapturasOab.mockResolvedValue([other, matching]);
    const terminal = vi.fn();
    const { result } = renderHook(() => useOabCapture("account-1", vi.fn(), terminal));
    await waitFor(() => expect(result.current.phase).toBe("completed"));
    expect(result.current.job?.id).toBe(42);
    expect(sessionStorage.getItem("causor:capture-attempt:account-1")).toBeNull();
    expect(terminal).toHaveBeenCalledTimes(1);
  });

  it("ignores an old A response after A to B to A and keeps the new operation locked", async () => {
    let resolveOld!: (value: ReturnType<typeof job>[]) => void;
    let resolveNew!: (value: ReturnType<typeof job>[]) => void;
    api.listarCapturasOab.mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; }))
      .mockResolvedValueOnce([])
      .mockImplementationOnce(() => new Promise((resolve) => { resolveNew = resolve; }));
    const { result, rerender } = renderHook(({ account }) => useOabCapture(account, vi.fn(), vi.fn()),
      { initialProps: { account: "A" } });
    await waitFor(() => expect(api.listarCapturasOab).toHaveBeenCalledTimes(1));
    rerender({ account: "B" });
    await waitFor(() => expect(api.listarCapturasOab).toHaveBeenCalledTimes(2));
    rerender({ account: "A" });
    await waitFor(() => expect(api.listarCapturasOab).toHaveBeenCalledTimes(3));
    await act(async () => { resolveOld([job("completed", { intimacoes_novas: 99 })]); });
    await act(async () => { await result.current.submit("249340", "SP"); });
    expect(api.iniciarCapturaOab).not.toHaveBeenCalled();
    await act(async () => { resolveNew([]); });
    expect(result.current.job).toBeNull();
  });
});
