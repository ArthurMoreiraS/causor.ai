// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Intimacao, IntimacaoAnalysis } from "@/lib/api";

const query = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ consultarAnalisesPrazo: query }));
import { useDeadlineAnalysis } from "./useDeadlineAnalysis";

const notice = (id = 1, job = 10): Intimacao => ({
  id, processo_id: 1, fonte: "DJEN", numero_processo: "123", tribunal: "TJSP",
  tipo_comunicacao: "Intimação", teor: "Texto jurídico", data_disponibilizacao: null,
  data_publicacao: null, prazo_analise: { status: "analisando", job_id: job },
});
const pending = [{ id: 1, prazo_analise: { status: "analisando", job_id: 10 } }];
const done = [{ id: 1, prazo_analise: { status: "calculado_a_revisar", job_id: 10, prazo_id: 20 } }];
const advance = async (milliseconds = 5000) => { await act(async () => { await vi.advanceTimersByTimeAsync(milliseconds); }); };

describe("deadline state polling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(document, "hidden", "get").mockReturnValue(false);
    query.mockResolvedValue(pending);
  });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.resetAllMocks(); });

  it("queries only pending IDs, updates badges and refreshes once at completion", async () => {
    const states = vi.fn();
    const complete = vi.fn().mockResolvedValue(true);
    renderHook(() => useDeadlineAnalysis("user", [notice()], states, complete));
    await advance();
    expect(query).toHaveBeenCalledWith([1]);
    expect(states).toHaveBeenCalledWith(pending, new Map([[1, 10]]));
    expect(complete).not.toHaveBeenCalled();
    query.mockResolvedValue(done);
    await advance();
    expect(complete).toHaveBeenCalledTimes(1);
    await advance(20000);
    expect(query).toHaveBeenCalledTimes(2);
  });

  it("never overlaps slow requests", async () => {
    let resolve!: (value: IntimacaoAnalysis[]) => void;
    query.mockReturnValue(new Promise<IntimacaoAnalysis[]>(r => { resolve = r; }));
    renderHook(() => useDeadlineAnalysis("user", [notice()], vi.fn(), vi.fn()));
    await advance(30000);
    expect(query).toHaveBeenCalledTimes(1);
    await act(async () => { resolve(pending); });
    query.mockResolvedValue(pending);
    await advance();
    expect(query).toHaveBeenCalledTimes(2);
  });

  it("pauses in a hidden tab and resumes on visibility", async () => {
    const hidden = vi.spyOn(document, "hidden", "get").mockReturnValue(true);
    renderHook(() => useDeadlineAnalysis("user", [notice()], vi.fn(), vi.fn()));
    await advance(30000);
    expect(query).not.toHaveBeenCalled();
    hidden.mockReturnValue(false);
    await act(async () => { document.dispatchEvent(new Event("visibilitychange")); });
    expect(query).toHaveBeenCalledTimes(1);
    hidden.mockReturnValue(true);
    await act(async () => { document.dispatchEvent(new Event("visibilitychange")); });
    await advance(30000);
    expect(query).toHaveBeenCalledTimes(1);
  });

  it("retries failed status or dashboard requests and notices removed by cleanup", async () => {
    const complete = vi.fn().mockResolvedValueOnce(false).mockResolvedValue(true);
    query.mockRejectedValueOnce(new Error("offline")).mockResolvedValue([]);
    renderHook(() => useDeadlineAnalysis("user", [notice()], vi.fn(), complete));
    await advance();
    expect(complete).not.toHaveBeenCalled();
    await advance();
    expect(complete).toHaveBeenCalledTimes(1);
    await advance();
    expect(complete).toHaveBeenCalledTimes(2);
    await advance();
    expect(query).toHaveBeenCalledTimes(3);
  });

  it("discards a response from before a retry or account change", async () => {
    let resolve!: (value: IntimacaoAnalysis[]) => void;
    query.mockReturnValue(new Promise<IntimacaoAnalysis[]>(r => { resolve = r; }));
    const states = vi.fn();
    const complete = vi.fn();
    const { rerender } = renderHook(({ user, job }) =>
      useDeadlineAnalysis(user, [notice(1, job)], states, complete),
    { initialProps: { user: "first", job: 10 } });
    await advance();
    rerender({ user: "second", job: 20 });
    await act(async () => { resolve(done); });
    expect(states).not.toHaveBeenCalled();
    expect(complete).not.toHaveBeenCalled();
    query.mockResolvedValue([{ id: 1, prazo_analise: { status: "analisando", job_id: 20 } }]);
    await advance();
    expect(states).toHaveBeenCalledWith(expect.anything(), new Map([[1, 20]]));
  });

  it("does not poll without an account or active analyses", async () => {
    const { rerender } = renderHook(({ user, notices }) =>
      useDeadlineAnalysis(user, notices, vi.fn(), vi.fn()),
    { initialProps: { user: undefined as string | undefined, notices: [notice()] } });
    await advance();
    rerender({ user: "user", notices: [] });
    await advance();
    expect(query).not.toHaveBeenCalled();
  });

  it("reconciles a retry made in another tab instead of polling the old job forever", async () => {
    query.mockResolvedValue([{ id: 1, prazo_analise: { status: "analisando", job_id: 20 } }]);
    const complete = vi.fn().mockResolvedValue(false);
    const states = vi.fn();
    renderHook(() => useDeadlineAnalysis("user", [notice()], states, complete));
    await advance();
    expect(complete).toHaveBeenCalledTimes(1);
    expect(states).not.toHaveBeenCalled();
  });
});
