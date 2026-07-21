// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import MniSection from "./MniSection";
import {
  cadastrarMniCredencial,
  listarMniCredenciais,
  revogarMniCredencial,
  testarMniCredencial
} from "@/lib/api";

vi.mock("@/lib/api", () => ({
  listarMniCredenciais: vi.fn(),
  cadastrarMniCredencial: vi.fn(),
  revogarMniCredencial: vi.fn(),
  testarMniCredencial: vi.fn()
}));

beforeEach(() => {
  vi.mocked(listarMniCredenciais).mockResolvedValue([
    {
      id: 1,
      tribunal: "TJMG",
      id_consultante_mask: "123***",
      ativo: true,
      last_validated_at: null
    }
  ]);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

test("lista credenciais mascaradas", async () => {
  render(<MniSection offline={false} />);
  expect(await screen.findByText("TJMG")).toBeInTheDocument();
  expect(screen.getByText("123***")).toBeInTheDocument();
  expect(screen.getByLabelText(/senha/i)).toBeInTheDocument();
});

test("cadastra credencial nova e recarrega a lista", async () => {
  vi.mocked(cadastrarMniCredencial).mockResolvedValue({
    id: 2,
    tribunal: "TJBA",
    id_consultante_mask: "987***",
    ativo: true,
    last_validated_at: null
  });
  render(<MniSection offline={false} />);
  await screen.findByText("TJMG");
  fireEvent.change(screen.getByLabelText(/tribunal/i), { target: { value: "TJBA" } });
  fireEvent.change(screen.getByLabelText(/consultante/i), {
    target: { value: "98765432100" }
  });
  fireEvent.change(screen.getByLabelText(/senha/i), { target: { value: "s" } });
  fireEvent.click(screen.getByRole("button", { name: /cadastrar/i }));
  await waitFor(() =>
    expect(cadastrarMniCredencial).toHaveBeenCalledWith({
      tribunal: "TJBA",
      id_consultante: "98765432100",
      senha: "s"
    })
  );
});

test("revoga credencial", async () => {
  vi.mocked(revogarMniCredencial).mockResolvedValue(undefined);
  render(<MniSection offline={false} />);
  await screen.findByText("TJMG");
  fireEvent.click(screen.getByRole("button", { name: /revogar/i }));
  await waitFor(() => expect(revogarMniCredencial).toHaveBeenCalledWith(1));
});

test("testa credencial com numero de processo", async () => {
  vi.mocked(testarMniCredencial).mockResolvedValue({
    ok: true,
    error_code: null,
    documentos: 3
  });
  render(<MniSection offline={false} />);
  await screen.findByText("TJMG");
  fireEvent.change(screen.getByLabelText(/processo para teste/i), {
    target: { value: "0000000-00.2026.8.13.0000" }
  });
  fireEvent.click(screen.getByRole("button", { name: /testar/i }));
  await waitFor(() =>
    expect(testarMniCredencial).toHaveBeenCalledWith(1, "0000000-00.2026.8.13.0000")
  );
  expect(await screen.findByText(/3 documento/)).toBeInTheDocument();
});
