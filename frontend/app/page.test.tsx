// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  loadDashboard: vi.fn(), listarOabsMonitoradas: vi.fn(), listarCapturasOab: vi.fn(),
  iniciarCapturaOab: vi.fn(), consultarCapturaOab: vi.fn(), listarClientes: vi.fn(),
  analisarPrazosExistentes: vi.fn(), repetirAnalisePrazo: vi.fn(), removerDadosOab: vi.fn()
}));
const toast = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/api")>(), ...api
}));
vi.mock("@/lib/supabase", () => ({ supabase: { auth: { getSession: vi.fn().mockResolvedValue({ data: { session: null } }) } } }));
vi.mock("./AuthProvider", () => ({ useRequireAuth: () => ({
  loading: false, session: { user: { id: "user-1", email: "lawyer@example.com" } }, signOut: vi.fn()
}) }));
vi.mock("./components/Toast", () => ({ useToast: () => toast }));
vi.mock("next/image", () => ({ default: () => null }));
vi.mock("@/lib/work-api", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/work-api")>(),
  listarTrabalhos: vi.fn().mockResolvedValue({ total: 0, items: [] }),
  obterTrabalho: vi.fn()
}));

import Home from "./page";

const captureJob = (status: "queued" | "completed") => ({
  id: 17, tipo: "captura_oab", status, entidade: "escritorio", entidade_id: 1,
  payload: { oab: "249340", uf: "SP", request_id: "attempt-1" },
  resultado: status === "completed" ? { intimacoes_novas: 3, prazos_registrados: 1 } : null,
  erro: null, created_at: new Date().toISOString(), updated_at: new Date().toISOString()
});
const dashboard = { intimacoes: [], processos: [], prazos: [], peticoes: [] };

describe("Home OAB capture modal", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    window.history.replaceState(null, "", "/");
    api.loadDashboard.mockResolvedValue(dashboard);
    api.listarClientes.mockResolvedValue({ total: 0, items: [] });
    api.listarOabsMonitoradas.mockResolvedValue([]);
    api.listarCapturasOab.mockResolvedValue([]);
    api.iniciarCapturaOab.mockImplementation(async () => {
      api.listarOabsMonitoradas.mockResolvedValue([{ id: 1, oab: "249340", uf: "SP", ativo: true }]);
      return captureJob("queued");
    });
    api.consultarCapturaOab.mockResolvedValue(captureJob("completed"));
  });
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

  it("does not show historical capture feedback without monitored OABs, including after reopening", async () => {
    api.listarCapturasOab.mockResolvedValue([captureJob("completed")]);
    render(<Home />);
    fireEvent.click(screen.getAllByRole("button", { name: "Captura por OAB" })[0]);
    await waitFor(() => expect(api.listarOabsMonitoradas).toHaveBeenCalled());
    await screen.findByText("Nenhuma OAB cadastrada.");
    expect(screen.queryByText(/OAB 249340\/SP: captura concluída/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Verificar agora" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Fechar" }));
    fireEvent.click(screen.getAllByRole("button", { name: "Captura por OAB" })[0]);
    expect(screen.queryByText(/OAB 249340\/SP: captura concluída/)).toBeNull();
  });

  it("removes a monitored OAB and clears its feedback after confirmation", async () => {
    api.listarOabsMonitoradas.mockResolvedValue([{ id: 1, oab: "249340", uf: "SP", ativo: true }]);
    api.listarCapturasOab.mockResolvedValue([captureJob("completed")]);
    api.removerDadosOab.mockImplementation(async () => {
      api.listarOabsMonitoradas.mockResolvedValue([]);
      return { removidos: { intimacoes: 13, processos: 9 } };
    });
    render(<Home />);
    fireEvent.click(screen.getAllByRole("button", { name: "Captura por OAB" })[0]);
    fireEvent.click(await screen.findByRole("button", { name: "Remover OAB e dados" }));
    const confirmation = screen.getByRole("dialog");
    fireEvent.click(within(confirmation).getByRole("button", { name: "Remover OAB e dados" }));
    await waitFor(() => expect(api.removerDadosOab).toHaveBeenCalledWith("249340", "SP"));
    await screen.findByText("Nenhuma OAB cadastrada.");
    expect(screen.queryByText(/OAB 249340\/SP: captura concluída/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Verificar agora" })).toBeNull();
    await waitFor(() => expect(api.loadDashboard).toHaveBeenCalledTimes(2));
  });

  it("keeps tracking after close and reopen, then finishes before dashboard refresh", async () => {
    render(<Home />);
    await waitFor(() => expect(api.loadDashboard).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(api.listarCapturasOab).toHaveBeenCalledTimes(1));
    await act(async () => {});
    fireEvent.click(screen.getAllByRole("button", { name: "Captura por OAB" })[0]);
    const modal = () => screen.getByRole("heading", { name: "Captura por OAB" }).closest(".modalCard") as HTMLElement;
    await waitFor(() => expect(api.listarCapturasOab).toHaveBeenCalledTimes(2));
    await act(async () => {});
    fireEvent.change(within(modal()).getByPlaceholderText("Número da OAB"), { target: { value: "249340" } });
    fireEvent.click(within(modal()).getByRole("button", { name: "Capturar" }));
    await waitFor(() => expect(within(modal()).getByRole("status").textContent).toContain("aguardando início"));
    expect(api.iniciarCapturaOab).toHaveBeenCalledTimes(1);

    fireEvent.click(within(modal()).getByRole("button", { name: "Fechar" }));
    expect(screen.queryByRole("heading", { name: "Captura por OAB" })).toBeNull();
    fireEvent.click(screen.getAllByRole("button", { name: "Captura por OAB" })[0]);
    expect(within(modal()).getByRole("status").textContent).toContain("aguardando início");
    expect(api.iniciarCapturaOab).toHaveBeenCalledTimes(1);

    let releaseRefresh!: (value: typeof dashboard) => void;
    api.loadDashboard.mockImplementationOnce(() => new Promise((resolve) => { releaseRefresh = resolve; }));
    await act(async () => { fireEvent.click(within(modal()).getByRole("button", { name: "Verificar agora" })); });
    await waitFor(() => expect(toast).toHaveBeenCalledWith(expect.objectContaining({ title: "Captura concluída" })));
    expect(screen.queryByRole("heading", { name: "Captura por OAB" })).toBeNull();
    expect(api.loadDashboard).toHaveBeenCalledTimes(2);
    expect(api.iniciarCapturaOab).toHaveBeenCalledTimes(1);
    await act(async () => { releaseRefresh(dashboard); });
  });
});

it("retoma backfill após resposta perdida sem recomeçar o cursor", async () => {
  localStorage.clear();
  api.loadDashboard.mockResolvedValue(dashboard);
  api.listarClientes.mockResolvedValue({ total: 0, items: [] });
  api.listarOabsMonitoradas.mockResolvedValue([]);
  api.listarCapturasOab.mockResolvedValue([]);
  api.analisarPrazosExistentes.mockResolvedValueOnce({ enfileiradas: 1, ultimo_id: 100, ha_mais: true })
    .mockRejectedValueOnce(new Error("resposta perdida"))
    .mockResolvedValueOnce({ enfileiradas: 0, ultimo_id: 150, ha_mais: false });
  render(<Home />);
  fireEvent.click((await screen.findAllByRole("button", { name: "Intimações" }))[0]);
  fireEvent.click(await screen.findByRole("button", { name: "Analisar prazos já capturados" }));
  await waitFor(() => expect(screen.getByText(/Interrompido\. Use Continuar análise/)).toBeTruthy());
  expect(localStorage.getItem("causor-prazo-backfill-user-1")).toBe("100");
  fireEvent.click(screen.getByRole("button", { name: "Continuar análise" }));
  await waitFor(() => expect(api.analisarPrazosExistentes).toHaveBeenCalledTimes(3));
  expect(api.analisarPrazosExistentes.mock.calls.map(call => call[0])).toEqual([0, 100, 100]);
  await waitFor(() => expect(localStorage.getItem("causor-prazo-backfill-user-1")).toBeNull());
  cleanup();
});

it("abre a preparação pela intimação, protege edição e retoma a origem pela URL", async () => {
  api.listarClientes.mockResolvedValue({ total: 0, items: [] });
  const notice = { id: 8, processo_id: 4, fonte: "DJEN", numero_processo: "00000000020268260000",
    tribunal: "TJSP", tipo_comunicacao: "Intimação", teor: "Prazo para manifestação", data_disponibilizacao: "2026-09-25", data_publicacao: null };
  const process = { id: 4, numero: notice.numero_processo, classe: null, tribunal: "TJSP", orgao_julgador: null, sistema: null };
  api.loadDashboard.mockResolvedValue({ ...dashboard, intimacoes: [notice], processos: [process], reviewQueue: [
    { intimacao: notice, processo: process, prazo: null, peticao: null, status: "capturada", risco: "sem_prazo", dias_para_vencer: null }
  ] });
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  try {
    render(<Home />);
    await waitFor(() => expect(screen.getAllByRole("button", { name: "Intimações" }).length).toBeGreaterThan(0));
    fireEvent.click(screen.getAllByRole("button", { name: "Intimações" })[0]);
    fireEvent.click(await screen.findByRole("button", { name: "Preparar minuta" }));
    expect(window.location.search).toContain("intimacao=8");
    expect((screen.getByLabelText("Processo") as HTMLSelectElement).value).toBe("4");
    fireEvent.change(screen.getByLabelText("Providência"), { target: { value: "Manifestar sobre o laudo" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Intimações" })[0]);
    expect(confirm).toHaveBeenCalled();
    expect(screen.getByLabelText("Providência")).toBeTruthy();
    cleanup();
    confirm.mockRestore();
    render(<Home />);
    expect((await screen.findByLabelText("Processo") as HTMLSelectElement).value).toBe("4");
    expect(screen.getByText(/Intimação #8 vinculada/)).toBeTruthy();
  } finally { confirm.mockRestore(); cleanup(); window.history.replaceState(null, "", "/"); }
});
