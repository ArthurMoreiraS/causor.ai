// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { consultarOperacaoAtual, consultarOperacaoTrabalho, iniciarOperacaoTrabalho, obterTrabalhoAposOperacao,
  type OperacaoTrabalho, type Trabalho } from "@/lib/work-api";
import { useWorkOperation } from "./useWorkOperation";

vi.mock("@/lib/work-api", () => ({ consultarOperacaoAtual: vi.fn(), consultarOperacaoTrabalho: vi.fn(),
  iniciarOperacaoTrabalho: vi.fn(), obterTrabalhoAposOperacao: vi.fn() }));

const work = { id: 1, versao: 3, processo_id: 2 } as Trabalho;
const completed: OperacaoTrabalho = { id: 5, trabalho_id: 1, acao: "minuta", versao: 3,
  request_id: "old", request_ids: ["old"], status: "completed", erro: null,
  resultado: { trabalho_id: 1, versao: 4, peticao_id: 9 }, created_at: null };

beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); });
afterEach(cleanup);

it("retoma conclusão após refresh sem abrir automaticamente a peça", async () => {
  vi.mocked(consultarOperacaoAtual).mockResolvedValue(completed);
  vi.mocked(obterTrabalhoAposOperacao).mockResolvedValue({ ...work, versao: 4 });
  const saved = vi.fn(); const open = vi.fn();
  renderHook(() => useWorkOperation(work, saved, open));
  await waitFor(() => expect(saved).toHaveBeenCalledWith({ ...work, versao: 4 }));
  expect(open).not.toHaveBeenCalled();
  expect(iniciarOperacaoTrabalho).not.toHaveBeenCalled();
});

it("recupera POST perdido pelo mesmo request_id e não inicia outra minuta", async () => {
  vi.mocked(consultarOperacaoAtual).mockResolvedValueOnce(null).mockImplementation(async () => ({
    ...completed, request_id: requestedId, request_ids: [requestedId] }));
  vi.mocked(obterTrabalhoAposOperacao).mockResolvedValue({ ...work, versao: 4 });
  let requestedId = "";
  vi.mocked(iniciarOperacaoTrabalho).mockImplementation(async (_work, _action, id) => {
    requestedId = id; throw new Error("Tempo de resposta excedido");
  });
  const saved = vi.fn(); const open = vi.fn();
  const { result } = renderHook(() => useWorkOperation(work, saved, open));
  await act(async () => { await result.current.start("minuta"); });
  expect(saved).toHaveBeenCalledTimes(1);
  expect(open).toHaveBeenCalledWith(9);
  expect(iniciarOperacaoTrabalho).toHaveBeenCalledTimes(1);
});

it("descarta resposta antiga após navegar A→B→A", async () => {
  let finish!: (value: OperacaoTrabalho | null) => void;
  vi.mocked(consultarOperacaoAtual).mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }))
    .mockResolvedValue(null);
  const saved = vi.fn();
  const { rerender } = renderHook(({ value }) => useWorkOperation(value, saved, vi.fn()),
    { initialProps: { value: work } });
  rerender({ value: { ...work, id: 2 } });
  rerender({ value: work });
  await act(async () => finish(completed));
  expect(saved).not.toHaveBeenCalled();
});

it("tenta novamente o GET final perdido sem criar outra minuta", async () => {
  vi.useFakeTimers();
  try {
    vi.mocked(consultarOperacaoAtual).mockResolvedValue(completed);
    vi.mocked(consultarOperacaoTrabalho).mockResolvedValue(completed);
    vi.mocked(obterTrabalhoAposOperacao).mockRejectedValueOnce(new Error("Rede indisponível"))
      .mockResolvedValue({ ...work, versao: 4 });
    const saved = vi.fn();
    renderHook(() => useWorkOperation(work, saved, vi.fn()));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(saved).not.toHaveBeenCalled();
    await act(async () => { await vi.advanceTimersByTimeAsync(2100); });
    expect(saved).toHaveBeenCalledTimes(1);
    expect(iniciarOperacaoTrabalho).not.toHaveBeenCalled();
  } finally { vi.useRealTimers(); }
});

it("falha terminal permite nova solicitação explícita", async () => {
  vi.mocked(consultarOperacaoAtual).mockResolvedValue(null);
  const ids: string[] = [];
  vi.mocked(iniciarOperacaoTrabalho).mockImplementation(async (_work, _action, id) => {
    ids.push(id);
    return { ...completed, request_id: id, request_ids: [id], status: "failed", resultado: null,
      erro: "Tente novamente" };
  });
  const { result } = renderHook(() => useWorkOperation(work, vi.fn(), vi.fn()));
  await act(async () => { await result.current.start("minuta"); });
  await act(async () => { await result.current.start("minuta"); });
  expect(ids).toHaveLength(2);
  expect(ids[0]).not.toBe(ids[1]);
});
