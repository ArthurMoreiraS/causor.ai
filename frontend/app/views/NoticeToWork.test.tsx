// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { IntimacaoRow } from "@/lib/views";
import { listarClientes } from "@/lib/api";
import { criarTrabalho, listarTrabalhos, obterTrabalho } from "@/lib/work-api";
import IntimacoesView from "./IntimacoesView";
import TrabalhosView from "./TrabalhosView";

vi.mock("@/lib/api", () => ({ listarClientes: vi.fn(), criarCliente: vi.fn() }));
vi.mock("@/lib/work-api", () => ({ criarTrabalho: vi.fn(), listarTrabalhos: vi.fn(), obterTrabalho: vi.fn(), atualizarTrabalho: vi.fn(), criarProcesso: vi.fn() }));
vi.mock("../components/ProcessContextStatus", () => ({ default: () => null }));
vi.mock("../components/DocumentUploadDialog", () => ({ default: () => null }));
vi.mock("../components/WorkEvidence", () => ({ default: () => null }));
vi.mock("../components/WorkScope", () => ({ default: () => null }));
vi.mock("../components/WorkProtocol", () => ({ default: () => null }));
vi.mock("../components/WorkAssistant", () => ({ default: () => null }));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

const notice: IntimacaoRow = {
  intimacao: { id: 8, processo_id: 4, fonte: "djen", numero_processo: "0000000-00.2026.8.26.0000",
    tribunal: "TJSP", tipo_comunicacao: "Intimação", teor: "Ciência do ato", data_disponibilizacao: null, data_publicacao: "2026-09-25" },
  processo: { id: 4, numero: "0000000-00.2026.8.26.0000", classe: null, tribunal: "TJSP", orgao_julgador: null, sistema: null },
  prazo: { id: 9, processo_id: 4, intimacao_id: 8, descricao: "Manifestação", data_inicio: "2026-09-25", dias: 5,
    dias_uteis: true, data_fatal: "2026-10-02", cumprido: false },
  peticao: null
};

it("encaminha a intimação e o prazo para preparação do trabalho", () => {
  const onPrepareWork = vi.fn();
  render(<IntimacoesView rows={[notice]} offline={false} onOpen={vi.fn()} onPrepareWork={onPrepareWork} />);
  fireEvent.click(screen.getByRole("button", { name: "Preparar trabalho" }));
  expect(onPrepareWork).toHaveBeenCalledWith(8, 4, 9);
});

it("cria o trabalho com a origem capturada, sem presumir a providência", async () => {
  vi.mocked(listarClientes).mockResolvedValue({ total: 0, items: [] });
  vi.mocked(listarTrabalhos).mockResolvedValue({ total: 0, items: [] });
  vi.mocked(criarTrabalho).mockResolvedValue({ id: 12, processo_id: 4, intimacao_id: 8, prazo_id: 9,
    peticao_id: null, responsavel_id: null, providencia: "Manifestar sobre o laudo", instrucoes: "", grau: "1",
    polo: null, versao: 1, escopo: null, evidencias: null, created_at: "", updated_at: "" });
  vi.mocked(obterTrabalho).mockImplementation(async () => await vi.mocked(criarTrabalho).mock.results[0].value);
  render(<TrabalhosView processos={[notice.processo!]} offline={false} initialProcessId={4}
    initialOrigin={{ intimacaoId: 8, prazoId: 9 }} onChanged={vi.fn()} onDocuments={vi.fn()} onOpenDraft={vi.fn()} />);
  expect(screen.getByText(/Intimação #8 vinculada/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Providência"), { target: { value: "Manifestar sobre o laudo" } });
  fireEvent.click(screen.getByRole("button", { name: "Criar trabalho" }));
  await waitFor(() => expect(criarTrabalho).toHaveBeenCalledWith(expect.objectContaining({
    processo_id: 4, intimacao_id: 8, prazo_id: 9, providencia: "Manifestar sobre o laudo"
  })));
});
