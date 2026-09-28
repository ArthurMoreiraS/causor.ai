// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  loadDashboard: vi.fn(), listarOabsMonitoradas: vi.fn(), listarCapturasOab: vi.fn(),
  iniciarCapturaOab: vi.fn(), consultarCapturaOab: vi.fn()
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
    window.history.replaceState(null, "", "/");
    api.loadDashboard.mockResolvedValue(dashboard);
    api.listarOabsMonitoradas.mockResolvedValue([]);
    api.listarCapturasOab.mockResolvedValue([]);
    api.iniciarCapturaOab.mockResolvedValue(captureJob("queued"));
    api.consultarCapturaOab.mockResolvedValue(captureJob("completed"));
  });
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

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
