// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { baixarFonteCitada, enviarAutos, listarTrechosDocumento, listarVersoesDocumento, type DocumentoVersao, type Tarefa } from "@/lib/api";
import DocumentUploadDialog from "./DocumentUploadDialog";
import DocumentEvidenceDialog from "./DocumentEvidenceDialog";

vi.mock("@/lib/api", () => ({ baixarFonteCitada: vi.fn(), enviarAutos: vi.fn(), listarTrechosDocumento: vi.fn(), listarVersoesDocumento: vi.fn() }));
const version: DocumentoVersao = { id: 9, sha256: "abc", mime_type: "application/pdf", size_bytes: 15, paginas: 3,
  atual: true, extracao: "complete", resumo_status: "complete", created_at: "2026-09-05T12:00:00Z" };
afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
  URL.createObjectURL = vi.fn(() => "blob:document-test");
  URL.revokeObjectURL = vi.fn();
  vi.mocked(listarVersoesDocumento).mockResolvedValue({ items: [version], total: 1 });
  vi.mocked(listarTrechosDocumento).mockResolvedValue({ items: [{ id: 3, pagina: 3, texto: "Comprovante de pagamento", ocr: false }],
    total: 1, resumo: "Pagamento documentado", citations: [{ chunk_id: 3, pagina: 3, quote: "Comprovante" }], versao: version });
  vi.mocked(baixarFonteCitada).mockResolvedValue(new Blob(["%PDF"], { type: "application/pdf" }));
});

it("envia documentos como complemento com a versão da tarefa conferida no formulário", async () => {
  const task = { id: 5, titulo: "Solicitar comprovante", processo_id: 2, versao: 7 } as Tarefa;
  vi.mocked(enviarAutos).mockResolvedValue({ id: 4 } as Awaited<ReturnType<typeof enviarAutos>>);
  const saved = vi.fn();
  render(<DocumentUploadDialog processos={[]} tarefa={task} offline={false} onClose={vi.fn()} onSaved={saved} />);
  expect(enviarAutos).not.toHaveBeenCalled();
  const file = new File(["%PDF"], "comprovante.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText("Arquivos PDF"), { target: { files: [file] } });
  fireEvent.change(screen.getByLabelText("Grau de destino"), { target: { value: "2" } });
  fireEvent.submit(screen.getByRole("button", { name: "Enviar documentos" }).closest("form")!);
  await waitFor(() => expect(saved).toHaveBeenCalled());
  expect(enviarAutos).toHaveBeenCalledWith(2, [file], "2", { tarefa: task, perfilResumo: "padrao" });
});

it("preserva o formulário e não declara recebimento quando há conflito de versão", async () => {
  vi.mocked(enviarAutos).mockRejectedValue(new Error("A tarefa mudou. Atualize antes de enviar."));
  const saved = vi.fn();
  render(<DocumentUploadDialog processos={[]} processoId={2} offline={false} onClose={vi.fn()} onSaved={saved} />);
  fireEvent.change(screen.getByLabelText("Arquivos PDF"), { target: { files: [new File(["pdf"], "teste.pdf")] } });
  fireEvent.submit(screen.getByRole("button", { name: "Enviar documentos" }).closest("form")!);
  await screen.findByRole("alert");
  expect(saved).not.toHaveBeenCalled();
  expect(screen.getByRole("dialog")).toBeTruthy();
});

it("herda segundo grau e impede trocar o processo ao receber documentos do trabalho", async () => {
  vi.mocked(enviarAutos).mockResolvedValue({ id: 4 } as Awaited<ReturnType<typeof enviarAutos>>);
  render(<DocumentUploadDialog processos={[]} processoId={2} initialDegree="2" fixedProcess offline={false} onClose={vi.fn()} onSaved={vi.fn()} />);
  expect((screen.getByLabelText("Processo de destino") as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText("Grau de destino") as HTMLSelectElement).value).toBe("2");
  const file = new File(["%PDF"], "autos.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText("Arquivos PDF"), { target: { files: [file] } });
  fireEvent.submit(screen.getByRole("button", { name: "Enviar documentos" }).closest("form")!);
  await waitFor(() => expect(enviarAutos).toHaveBeenCalledWith(2, [file], "2", { tarefa: undefined, perfilResumo: "padrao" }));
});

it("permite escolher resumo aprofundado antes do envio", async () => {
  vi.mocked(enviarAutos).mockResolvedValue({ id: 4 } as Awaited<ReturnType<typeof enviarAutos>>);
  render(<DocumentUploadDialog processos={[]} processoId={2} offline={false} onClose={vi.fn()} onSaved={vi.fn()} />);
  const file = new File(["%PDF"], "decisao.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText("Arquivos PDF"), { target: { files: [file] } });
  fireEvent.change(screen.getByLabelText("Resumo dos documentos"), { target: { value: "aprofundada" } });
  fireEvent.submit(screen.getByRole("button", { name: "Enviar documentos" }).closest("form")!);
  await waitFor(() => expect(enviarAutos).toHaveBeenCalledWith(2, [file], "1", { tarefa: undefined, perfilResumo: "aprofundada" }));
});

it("abre a versão histórica citada e navega até a página da evidência", async () => {
  render(<DocumentEvidenceDialog documentoId={2} nome="Comprovante" versaoId={4} onClose={vi.fn()} />);
  fireEvent.click((await screen.findAllByRole("button", { name: "Página 3" }))[0]);
  expect(baixarFonteCitada).toHaveBeenCalledWith(2, 4);
  expect(listarTrechosDocumento).toHaveBeenCalledWith(2, 4, "", 0);
  expect(screen.getByTitle("PDF de Comprovante").getAttribute("src")).toBe("blob:document-test#page=3");
  fireEvent.change(screen.getByLabelText("Buscar no texto extraído"), { target: { value: "pagamento" } });
  await waitFor(() => expect(listarTrechosDocumento).toHaveBeenCalledWith(2, 4, "pagamento", 0));
});

it("não incorpora conteúdo HTML como se fosse um PDF", async () => {
  vi.mocked(baixarFonteCitada).mockResolvedValue(new Blob(["<script>bad()</script>"], { type: "text/html" }));
  render(<DocumentEvidenceDialog documentoId={2} nome="Arquivo" versaoId={9} onClose={vi.fn()} />);
  await screen.findByRole("alert");
  expect(screen.queryByTitle("PDF de Arquivo")).toBeNull();
  expect(URL.createObjectURL).not.toHaveBeenCalled();
});

it("lista os PDFs escolhidos, acrescenta novas escolhas, remove e ignora outros formatos", async () => {
  vi.mocked(enviarAutos).mockResolvedValue({ id: 4 } as Awaited<ReturnType<typeof enviarAutos>>);
  render(<DocumentUploadDialog processos={[]} processoId={2} offline={false} onClose={vi.fn()} onSaved={vi.fn()} />);
  const input = screen.getByLabelText("Arquivos PDF");
  const first = new File(["%PDF-1"], "inicial.pdf", { type: "application/pdf" });
  const second = new File(["%PDF-22"], "contestacao.pdf", { type: "application/pdf" });
  fireEvent.change(input, { target: { files: [first] } });
  fireEvent.change(input, { target: { files: [second, new File(["x"], "foto.png", { type: "image/png" })] } });
  expect(screen.getByText("inicial.pdf")).toBeTruthy();
  expect(screen.getByText("contestacao.pdf")).toBeTruthy();
  expect(screen.queryByText("foto.png")).toBeNull();
  expect(screen.getByRole("alert").textContent).toMatch(/1 arquivo ignorado/);
  expect(screen.getByText(/2 arquivos ·/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Remover inicial.pdf" }));
  fireEvent.submit(screen.getByRole("button", { name: "Enviar documentos" }).closest("form")!);
  await waitFor(() => expect(enviarAutos).toHaveBeenCalledWith(2, [second], "1", { tarefa: undefined, perfilResumo: "padrao" }));
});
