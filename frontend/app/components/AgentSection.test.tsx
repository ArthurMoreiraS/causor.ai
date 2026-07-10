// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import AgentSection, { isOnline, pairingCommand } from "./AgentSection";

vi.mock("@/lib/api", () => ({
  listarAgentes: vi.fn().mockResolvedValue([
    {
      id: 1,
      nome: "Notebook jurídico",
      ativo: true,
      last_seen_at: "2026-07-10T12:00:00Z",
      version: "0.1.0"
    }
  ]),
  criarCodigoPareamento: vi.fn(),
  revogarAgente: vi.fn()
}));

test("shows paired agent health", async () => {
  render(<AgentSection offline={false} />);
  expect(await screen.findByText("Notebook jurídico")).toBeInTheDocument();
  expect(screen.getByText(/0.1.0/)).toBeInTheDocument();
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
