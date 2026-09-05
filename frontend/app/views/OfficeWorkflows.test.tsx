// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { atualizarTarefa, criarCliente, listarClientes, listarTarefas, vincularCliente, type Tarefa } from "@/lib/api";
import type { PeticaoRow } from "@/lib/views";
import ClientesView from "./ClientesView";
import TarefasView from "./TarefasView";
import GateOabView from "./GateOabView";

vi.mock("@/lib/api", () => ({ atualizarTarefa: vi.fn(), criarCliente: vi.fn(), listarClientes: vi.fn(),
  listarTarefas: vi.fn(), vincularCliente: vi.fn() }));
afterEach(cleanup);
beforeEach(() => vi.clearAllMocks());

it("cadastra cliente, vincula processo e prepara tarefa com o mesmo cliente", async () => {
  const customer = { id: 4, nome: "Cliente teste", documento: null, processos_count: 0 };
  vi.mocked(listarClientes).mockResolvedValue({ items: [], total: 0 });
  vi.mocked(criarCliente).mockResolvedValue(customer);
  vi.mocked(vincularCliente).mockResolvedValue({ processo_id: 9, cliente_id: 4 });
  const changed = vi.fn(), newTask = vi.fn();
  render(<ClientesView offline={false} refreshKey={0} processos={[{ id: 9, numero: "123", cliente_id: null,
    classe: null, tribunal: null, orgao_julgador: null, sistema: null }]}
    onChanged={changed} onOpenProcess={vi.fn()} onNewTask={newTask} />);
  fireEvent.click(screen.getByRole("button", { name: "Novo cliente" }));
  fireEvent.change(screen.getByLabelText("Nome ou razão social"), { target: { value: customer.nome } });
  fireEvent.click(screen.getByRole("button", { name: "Cadastrar cliente" }));
  await screen.findByRole("heading", { name: customer.nome });
  fireEvent.change(screen.getByLabelText("Vincular processo"), { target: { value: "9" } });
  fireEvent.click(screen.getByRole("button", { name: "Vincular cliente representado" }));
  await waitFor(() => expect(changed).toHaveBeenCalled());
  expect(vincularCliente).toHaveBeenCalledWith(9, 4);
  fireEvent.click(screen.getByRole("button", { name: "Nova tarefa para este cliente" }));
  expect(newTask).toHaveBeenCalledWith(expect.objectContaining({ cliente_id: 4, tipo: "atendimento" }), customer.nome);
});

it("abre a minuta de origem e mantém a tarefa pendente se a conclusão falhar", async () => {
  const task = { id: 1, titulo: "Obter comprovante", tipo: "documento", prioridade: "normal", status: "aberta",
    versao: 3, peticao_id: 8, origem_texto: "Falta comprovante" } as Tarefa;
  vi.mocked(listarTarefas).mockResolvedValue({ items: [task], total: 1 });
  vi.mocked(atualizarTarefa).mockRejectedValue(new Error("A tarefa foi alterada. Atualize a lista."));
  const openDraft = vi.fn();
  render(<TarefasView offline={false} refreshKey={0} onNew={vi.fn()} onEdit={vi.fn()}
    onOpenProcess={vi.fn()} onOpenNotice={vi.fn()} onOpenDraft={openDraft} />);
  fireEvent.click(await screen.findByRole("button", { name: "Minuta de origem" }));
  expect(openDraft).toHaveBeenCalledWith(8);
  fireEvent.click(screen.getByRole("button", { name: "Concluir" }));
  await screen.findByRole("alert");
  expect(atualizarTarefa).toHaveBeenCalledWith(1, { versao: 3, status: "concluida" });
  expect((screen.getByRole("combobox", { name: "Situação de Obter comprovante" }) as HTMLSelectElement).value).toBe("aberta");
});

it("mantém minutas em revisão na fila de aprovação", () => {
  const row = { peticao: { id: 8, processo_id: 2, tipo: "Manifestação", status: "em_revisao" } } as PeticaoRow;
  const approve = vi.fn();
  render(<GateOabView rows={[row]} busy={null} offline={false} onApprove={approve} onFile={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Aprovar" }));
  expect(approve).toHaveBeenCalledWith(row.peticao);
});
