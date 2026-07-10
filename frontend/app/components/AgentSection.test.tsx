// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import AgentSection, { isOnline, pairingCommand } from "./AgentSection";
import { ToastProvider } from "./Toast";
import { listarAgentes, revogarAgente } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  listarAgentes: vi.fn(),
  criarCodigoPareamento: vi.fn(),
  revogarAgente: vi.fn()
}));

const agente = {
  id: 1,
  nome: "Notebook jurídico",
  ativo: true,
  last_seen_at: "2026-07-10T12:00:00Z",
  version: "0.1.0"
};

beforeEach(() => {
  vi.mocked(listarAgentes).mockResolvedValue([agente]);
  vi.mocked(revogarAgente).mockResolvedValue(undefined);
});

// Sem `globals: true` no vitest, o Testing Library não registra o cleanup
// automático — sem isto os renders acumulam entre testes.
afterEach(cleanup);

// useToast exige o provider; espelha o app real (ToastProvider no layout).
function renderSection() {
  return render(
    <ToastProvider>
      <AgentSection offline={false} />
    </ToastProvider>
  );
}

test("shows paired agent health", async () => {
  renderSection();
  expect(await screen.findByText("Notebook jurídico")).toBeInTheDocument();
  expect(screen.getByText(/0\.1\.0/)).toBeInTheDocument();
});

test("agent is online only within the 90s window", () => {
  const now = new Date("2026-07-10T12:01:00Z");
  expect(isOnline("2026-07-10T12:00:00Z", now)).toBe(true);
  expect(isOnline("2026-07-10T11:58:00Z", now)).toBe(false);
  expect(isOnline(null, now)).toBe(false);
});

test("pairing command embeds the one-time code and API base", () => {
  const command = pairingCommand("abc123");
  expect(command).toContain("python -m app.local_agent pair");
  expect(command).toContain("--code abc123");
  expect(command).toContain("--api http");
});

test("empty state invites the user to pair a computer", async () => {
  vi.mocked(listarAgentes).mockResolvedValue([]);
  renderSection();
  expect(await screen.findByText(/Nenhum computador pareado/)).toBeInTheDocument();
});

test("revoking asks for confirmation before calling the API", async () => {
  renderSection();
  fireEvent.click(await screen.findByRole("button", { name: "Revogar" }));
  expect(revogarAgente).not.toHaveBeenCalled();

  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByText(/Notebook jurídico/)).toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole("button", { name: /Revogar acesso/ }));
  await waitFor(() => expect(revogarAgente).toHaveBeenCalledWith(1));
});

test("revoked agents render without a revoke action", async () => {
  vi.mocked(listarAgentes).mockResolvedValue([
    { ...agente, ativo: false, last_seen_at: null }
  ]);
  renderSection();
  expect(await screen.findByText("Revogado")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Revogar" })).not.toBeInTheDocument();
});
