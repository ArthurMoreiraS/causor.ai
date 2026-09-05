// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { criarTarefa, listarUsuarios } from "@/lib/api";
import TarefaDialog from "./TarefaDialog";

vi.mock("@/lib/api", () => ({ criarTarefa: vi.fn(), atualizarTarefa: vi.fn(), listarUsuarios: vi.fn() }));
afterEach(cleanup);

describe("Tarefa a partir da revisão", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listarUsuarios).mockResolvedValue([]);
  });
  it("preserva a origem do alerta e só cria após confirmação", async () => {
    vi.mocked(criarTarefa).mockResolvedValue({ id: 7 } as Awaited<ReturnType<typeof criarTarefa>>);
    const saved = vi.fn();
    render(<TarefaDialog initial={{ titulo: "Conferir comprovante", processo_id: 2, peticao_id: 3,
      alerta_indice: 0, alerta_texto_esperado: "Comprovante ausente" }} processos={[]} offline={false} onClose={vi.fn()} onSaved={saved} />);
    expect(criarTarefa).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Data interna (opcional)"), { target: { value: "2026-10-02" } });
    fireEvent.click(screen.getByRole("button", { name: "Criar tarefa" }));
    await waitFor(() => expect(saved).toHaveBeenCalled());
    expect(criarTarefa).toHaveBeenCalledWith(expect.objectContaining({ processo_id: 2, peticao_id: 3,
      alerta_indice: 0, alerta_texto_esperado: "Comprovante ausente", data_prevista: "2026-10-02" }));
  });
  it("mantém o formulário aberto quando o servidor recusa a gravação", async () => {
    vi.mocked(criarTarefa).mockRejectedValue(new Error("Falha de teste"));
    const saved = vi.fn();
    render(<TarefaDialog initial={{ titulo: "Conferir" }} processos={[]} offline={false} onClose={vi.fn()} onSaved={saved} />);
    fireEvent.click(screen.getByRole("button", { name: "Criar tarefa" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(saved).not.toHaveBeenCalled();
  });
});
