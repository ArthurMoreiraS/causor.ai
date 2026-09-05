// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import AcessoTribunalWizard from "./AcessoTribunalWizard";
import { ToastProvider } from "./Toast";
import { loginTribunal, proximoPassoContexto, statusSessaoTribunal } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  proximoPassoContexto: vi.fn(),
  loginTribunal: vi.fn(),
  statusSessaoTribunal: vi.fn()
}));

const rota = { sistema: "PJe", tribunal: "TJMG", grau: "1" };

beforeEach(() => {
  vi.mocked(loginTribunal).mockResolvedValue({
    sistema: "PJe",
    tribunal: "TJMG",
    grau: "1",
    status: "conectando",
    command_id: 1
  });
  vi.mocked(statusSessaoTribunal).mockResolvedValue({ processo_id: 7, rotas: [] });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderWizard(onReady = vi.fn()) {
  return render(
    <ToastProvider>
      <AcessoTribunalWizard processoId={7} onReady={onReady} onClose={vi.fn()} />
    </ToastProvider>
  );
}

test("shows the court-login step and triggers the login command", async () => {
  vi.mocked(proximoPassoContexto).mockResolvedValue({
    processo_id: 7,
    ready: false,
    next_step: "court_login",
    rota
  });

  renderWizard();

  expect(await screen.findByText(/PJe · TJMG · 1º grau/)).toBeInTheDocument();
  fireEvent.click(await screen.findByRole("button", { name: /Abrir portal para login/ }));
  await waitFor(() => expect(loginTribunal).toHaveBeenCalledWith(7, "1", "PJe"));
});

test("guides pairing when no agent is online", async () => {
  vi.mocked(proximoPassoContexto).mockResolvedValue({
    processo_id: 7,
    ready: false,
    next_step: "pair_agent",
    rota
  });

  renderWizard();

  expect(await screen.findByText(/Nenhum computador pareado/)).toBeInTheDocument();
});

test("calls onReady when the context becomes ready", async () => {
  const onReady = vi.fn();
  vi.mocked(proximoPassoContexto).mockResolvedValue({
    processo_id: 7,
    ready: true,
    next_step: null,
    rota
  });

  renderWizard(onReady);

  await waitFor(() => expect(onReady).toHaveBeenCalled());
  expect(await screen.findByText(/Contexto disponível para revisão/)).toBeInTheDocument();
});

// O wizard repete a consulta a cada 4s. Sem trava, cada volta do polling
// dispararia `onReady` de novo — e quem escuta gera a minuta, ou seja, o
// advogado receberia varias minutas do mesmo processo.
test("onReady dispara uma vez so, mesmo com o polling continuando", async () => {
  vi.useFakeTimers();
  const onReady = vi.fn();
  vi.mocked(proximoPassoContexto).mockResolvedValue({
    processo_id: 7,
    ready: true,
    next_step: null,
    rota
  });

  renderWizard(onReady);

  await vi.advanceTimersByTimeAsync(20_000);
  vi.useRealTimers();

  expect(onReady).toHaveBeenCalledTimes(1);
});
