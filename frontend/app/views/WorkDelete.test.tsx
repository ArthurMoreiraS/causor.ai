// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { listarClientes } from "@/lib/api";
import { excluirTrabalho, listarTrabalhos, obterTrabalho, type Trabalho } from "@/lib/work-api";
import TrabalhosView from "./TrabalhosView";

vi.mock("@/lib/api", () => ({ listarClientes: vi.fn(), criarCliente: vi.fn(), vincularCliente: vi.fn() }));
vi.mock("@/lib/work-api", () => ({ criarTrabalho: vi.fn(), listarTrabalhos: vi.fn(), obterTrabalho: vi.fn(),
  atualizarTrabalho: vi.fn(), criarProcesso: vi.fn(), excluirTrabalho: vi.fn() }));
vi.mock("../components/ProcessContextStatus", () => ({ default: () => null }));
vi.mock("../components/DocumentUploadDialog", () => ({ default: () => null }));
vi.mock("../components/WorkEvidence", () => ({ default: () => null }));
vi.mock("../components/WorkScope", () => ({ default: () => null }));
vi.mock("../components/WorkAssistant", () => ({ default: () => null }));

const processo = { id: 4, numero: "50671771320264025101", classe: null, tribunal: "TRF2", orgao_julgador: null, sistema: null };
const work: Trabalho = { id: 7, processo_id: 4, intimacao_id: null, prazo_id: null, peticao_id: null, responsavel_id: null,
  providencia: "Teste", instrucoes: "", grau: "1", polo: null, versao: 3, escopo: null, evidencias: null, created_at: "", updated_at: "" };
const oldUrl = window.location.href;

beforeEach(() => {
  window.history.replaceState(null, "", "?trabalho=7");
  vi.mocked(listarClientes).mockResolvedValue({ total: 0, items: [] });
  vi.mocked(listarTrabalhos).mockResolvedValue({ total: 1, items: [work] });
  vi.mocked(obterTrabalho).mockResolvedValue(work);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.clearAllMocks(); window.history.replaceState(null, "", oldUrl); });

function renderView(canDelete: boolean, onDeleted = vi.fn(), onChanged = vi.fn()) {
  render(<TrabalhosView processos={[processo]} offline={false} onChanged={onChanged} onDocuments={vi.fn()}
    onOpenDraft={vi.fn()} canDelete={canDelete} onDeleted={onDeleted} />);
}

it("exclui o trabalho com a versão atual depois da confirmação", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const result = { trabalho_id: 7, minuta_excluida: false, tarefas_excluidas: 0, processo_removido: true };
  vi.mocked(excluirTrabalho).mockResolvedValue(result);
  const onDeleted = vi.fn();
  const onChanged = vi.fn();
  renderView(true, onDeleted, onChanged);
  fireEvent.click(await screen.findByRole("button", { name: "Excluir trabalho" }));
  await waitFor(() => expect(onDeleted).toHaveBeenCalledWith(result));
  expect(excluirTrabalho).toHaveBeenCalledWith(expect.objectContaining({ id: 7, versao: 3 }));
  expect(onChanged).toHaveBeenCalled();
  expect(screen.queryByRole("button", { name: "Excluir trabalho" })).toBeNull();
  expect(window.location.search).not.toContain("trabalho");
});

it("não exclui quando a confirmação é cancelada", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(false);
  renderView(true);
  fireEvent.click(await screen.findByRole("button", { name: "Excluir trabalho" }));
  expect(excluirTrabalho).not.toHaveBeenCalled();
});

it("mostra o erro do servidor e mantém o trabalho aberto", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.mocked(excluirTrabalho).mockRejectedValue(new Error("A minuta deste trabalho já foi aprovada."));
  renderView(true);
  fireEvent.click(await screen.findByRole("button", { name: "Excluir trabalho" }));
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Excluir trabalho" })).toBeTruthy();
});

it("esconde a exclusão de quem não tem permissão", async () => {
  renderView(false);
  await screen.findByText(/Processo .* 1º grau/);
  expect(screen.queryByRole("button", { name: "Excluir trabalho" })).toBeNull();
});
