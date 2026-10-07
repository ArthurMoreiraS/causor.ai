// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import type { IntimacaoRow } from "@/lib/views";
import { listarClientes, vincularCliente } from "@/lib/api";
import { criarTrabalho, listarTrabalhos, obterTrabalho } from "@/lib/work-api";
import IntimacoesView from "./IntimacoesView";
import TrabalhosView from "./TrabalhosView";

vi.mock("@/lib/api", () => ({ listarClientes: vi.fn(), criarCliente: vi.fn(), vincularCliente: vi.fn() }));
vi.mock("@/lib/work-api", () => ({ criarTrabalho: vi.fn(), listarTrabalhos: vi.fn(), obterTrabalho: vi.fn(), atualizarTrabalho: vi.fn(), criarProcesso: vi.fn() }));
vi.mock("../components/ProcessContextStatus", () => ({ default: () => null }));
vi.mock("../components/DocumentUploadDialog", () => ({ default: () => null }));
vi.mock("../components/WorkEvidence", () => ({ default: () => null }));
vi.mock("../components/WorkScope", () => ({ default: ({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) =>
  <button type="button" onClick={() => onDirtyChange(true)}>Editar índice</button> }));
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
  fireEvent.click(screen.getByRole("button", { name: "Preparar minuta" }));
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

it("abre um formulário limpo e ignora a retomada antiga que chega depois", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  const oldUrl = window.location.href;
  window.history.replaceState(null, "", "?trabalho=42");
  let resolveOld!: (value: Awaited<ReturnType<typeof obterTrabalho>>) => void;
  vi.mocked(obterTrabalho).mockReturnValue(new Promise(resolve => { resolveOld = resolve; }));
  vi.mocked(listarClientes).mockResolvedValue({ total: 0, items: [] });
  vi.mocked(listarTrabalhos).mockResolvedValue({ total: 0, items: [] });
  try {
    render(<TrabalhosView processos={[notice.processo!]} offline={false} onChanged={vi.fn()} onDocuments={vi.fn()} onOpenDraft={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Providência"), { target: { value: "Rascunho" } });
    fireEvent.click(screen.getByRole("button", { name: "Novo trabalho" }));
    expect((screen.getByLabelText("Providência") as HTMLInputElement).value).toBe("");
    expect((screen.getByLabelText("Processo") as HTMLSelectElement).value).toBe("");
    expect(window.location.search).not.toContain("trabalho");
    expect(document.activeElement?.id).toBe("work-objective");
    await act(async () => { resolveOld({ id: 42, processo_id: 4, providencia: "Trabalho antigo" } as Awaited<ReturnType<typeof obterTrabalho>>); });
    expect((screen.getByLabelText("Providência") as HTMLInputElement).value).toBe("");
  } finally { confirm.mockRestore(); window.history.replaceState(null, "", oldUrl); }
});

it("mostra a revisão de prazo diretamente na intimação sem prazo", () => {
  const open = vi.fn();
  render(<IntimacoesView rows={[{ ...notice, prazo: null }]} offline={false} onOpen={open} onPrepareWork={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Abrir prazo da intimação 8" }));
  expect(open).toHaveBeenCalledWith(8);
});

it("não descarta objetivo alterado ao trocar de trabalho sem confirmação", async () => {
  const first = { id: 1, processo_id: 4, providencia: "Original", instrucoes: "", grau: "1", polo: null, versao: 1 };
  const second = { ...first, id: 2, providencia: "Segundo" };
  vi.mocked(listarClientes).mockResolvedValue({ total: 0, items: [] });
  vi.mocked(listarTrabalhos).mockResolvedValue({ total: 2, items: [first, second] } as Awaited<ReturnType<typeof listarTrabalhos>>);
  vi.mocked(obterTrabalho).mockResolvedValue(first as Awaited<ReturnType<typeof obterTrabalho>>);
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  try {
    render(<TrabalhosView processos={[notice.processo!]} offline={false} onChanged={vi.fn()} onDocuments={vi.fn()} onOpenDraft={vi.fn()} />);
    await waitFor(() => expect(screen.getByRole("button", { name: /Original/ })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /Original/ }));
    fireEvent.change(screen.getByLabelText("Providência"), { target: { value: "Edição não salva" } });
    fireEvent.click(screen.getByRole("button", { name: /Segundo/ }));
    expect((screen.getByLabelText("Providência") as HTMLInputElement).value).toBe("Edição não salva");
    expect(confirm).toHaveBeenCalled();
  } finally { confirm.mockRestore(); }
});

it("carrega e pagina trabalhos em StrictMode", async () => {
  vi.mocked(listarClientes).mockResolvedValue({ total: 0, items: [] });
  vi.mocked(listarTrabalhos).mockImplementation(async (_processId, offset) => ({
    total: 51, items: [{ id: offset ? 2 : 1, processo_id: 4, providencia: offset ? "Página dois" : "Página um" }]
  }) as Awaited<ReturnType<typeof listarTrabalhos>>);
  render(<StrictMode><TrabalhosView processos={[notice.processo!]} offline={false} onChanged={vi.fn()} onDocuments={vi.fn()} onOpenDraft={vi.fn()} /></StrictMode>);
  expect(await screen.findByRole("button", { name: /Página um/ })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Próximos" }));
  expect(await screen.findByRole("button", { name: /Página dois/ })).toBeTruthy();
  expect(listarTrabalhos).toHaveBeenCalledWith(undefined, 50);
});

it("não substitui digitação feita enquanto a retomada responde", async () => {
  const oldUrl = window.location.href;
  window.history.replaceState(null, "", "?trabalho=42");
  let resolve!: (value: Awaited<ReturnType<typeof obterTrabalho>>) => void;
  vi.mocked(obterTrabalho).mockReturnValue(new Promise(done => { resolve = done; }));
  vi.mocked(listarClientes).mockResolvedValue({ total: 0, items: [] });
  vi.mocked(listarTrabalhos).mockResolvedValue({ total: 0, items: [] });
  try {
    render(<TrabalhosView processos={[notice.processo!]} offline={false} onChanged={vi.fn()} onDocuments={vi.fn()} onOpenDraft={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Providência"), { target: { value: "Edição iniciada" } });
    await act(async () => { resolve({ id: 42, processo_id: 4, providencia: "Versão remota" } as Awaited<ReturnType<typeof obterTrabalho>>); });
    expect((screen.getByLabelText("Providência") as HTMLInputElement).value).toBe("Edição iniciada");
  } finally { window.history.replaceState(null, "", oldUrl); }
});

it("atualiza versão remota sem edição local e preserva edição quando há conflito", async () => {
  const first = { id: 6, processo_id: 4, providencia: "Inicial", instrucoes: "", grau: "1", polo: null, versao: 1 };
  const second = { ...first, providencia: "Atualizada", versao: 2 };
  vi.mocked(listarClientes).mockResolvedValue({ total: 0, items: [] });
  vi.mocked(listarTrabalhos).mockResolvedValue({ total: 1, items: [first] } as Awaited<ReturnType<typeof listarTrabalhos>>);
  vi.mocked(obterTrabalho).mockResolvedValue(second as Awaited<ReturnType<typeof obterTrabalho>>);
  const callbacks = { onChanged: vi.fn(), onDocuments: vi.fn(), onOpenDraft: vi.fn() };
  const { rerender } = render(<TrabalhosView processos={[notice.processo!]} offline={false} {...callbacks} />);
  fireEvent.click(await screen.findByRole("button", { name: /Inicial/ }));
  await waitFor(() => expect((screen.getByLabelText("Providência") as HTMLInputElement).value).toBe("Atualizada"));
  fireEvent.change(screen.getByLabelText("Providência"), { target: { value: "Minha edição" } });
  vi.mocked(obterTrabalho).mockResolvedValue({ ...second, versao: 3 } as Awaited<ReturnType<typeof obterTrabalho>>);
  rerender(<TrabalhosView processos={[notice.processo!]} offline={false} {...callbacks} refreshKey={1} />);
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("outra sessão"));
  expect((screen.getByLabelText("Providência") as HTMLInputElement).value).toBe("Minha edição");
});

it("vincula cliente ao processo capturado e mantém o vínculo na retomada", async () => {
  const captured = { ...notice.processo!, cliente_id: null };
  const linked = { ...captured, cliente_id: 23 };
  const saved = { id: 30, processo_id: 4, intimacao_id: 8, prazo_id: 9, peticao_id: null, responsavel_id: null,
    providencia: "Responder intimação", instrucoes: "", grau: "1", polo: "Autor", versao: 1,
    escopo: null, evidencias: null, created_at: "", updated_at: "" };
  vi.mocked(listarClientes).mockResolvedValue({ total: 2, items: [{ id: 23, nome: "Maria" }, { id: 24, nome: "João" }] } as Awaited<ReturnType<typeof listarClientes>>);
  vi.mocked(listarTrabalhos).mockResolvedValue({ total: 1, items: [saved] });
  vi.mocked(obterTrabalho).mockResolvedValue(saved);
  vi.mocked(vincularCliente).mockResolvedValue({ processo_id: 4, cliente_id: 23 });
  const props = { offline: false, onChanged: vi.fn(), onDocuments: vi.fn(), onOpenDraft: vi.fn() };
  const { rerender, unmount } = render(<TrabalhosView processos={[captured]} {...props} />);
  fireEvent.click(await screen.findByRole("button", { name: /Responder intimação/ }));
  fireEvent.click(screen.getByRole("button", { name: "Vincular ou cadastrar cliente" }));
  fireEvent.change(screen.getByLabelText("Cliente representado"), { target: { value: "23" } });
  fireEvent.click(screen.getByRole("button", { name: "Salvar vínculo" }));
  await waitFor(() => expect(vincularCliente).toHaveBeenCalledWith(4, 23));
  expect(await screen.findByText("Maria")).toBeTruthy();
  rerender(<TrabalhosView processos={[{ ...captured, cliente_id: 24 }]} {...props} />);
  expect(await screen.findByText("João")).toBeTruthy();
  unmount();
  render(<TrabalhosView processos={[linked]} {...props} />);
  fireEvent.click(await screen.findByRole("button", { name: /Responder intimação/ }));
  expect(await screen.findByText("Maria")).toBeTruthy();
});

it("preserva o objetivo e o índice sujo durante atualização remota", async () => {
  const first = { id: 31, processo_id: 4, intimacao_id: null, prazo_id: null, peticao_id: null,
    responsavel_id: null, providencia: "Objetivo inicial", instrucoes: "", grau: "1", polo: "Autor",
    versao: 1, escopo: null, evidencias: null, created_at: "", updated_at: "" };
  vi.mocked(listarClientes).mockResolvedValue({ total: 0, items: [] });
  vi.mocked(listarTrabalhos).mockResolvedValue({ total: 1, items: [first] });
  vi.mocked(obterTrabalho).mockResolvedValue(first);
  const props = { processos: [notice.processo!], offline: false, onChanged: vi.fn(), onDocuments: vi.fn(), onOpenDraft: vi.fn() };
  const { rerender } = render(<TrabalhosView {...props} />);
  fireEvent.click(await screen.findByRole("button", { name: /Objetivo inicial/ }));
  fireEvent.click(screen.getByRole("button", { name: "Editar índice" }));
  vi.mocked(obterTrabalho).mockResolvedValue({ ...first, providencia: "Remoto", versao: 2 });
  rerender(<TrabalhosView {...props} refreshKey={1} />);
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("outra sessão"));
  expect((screen.getByLabelText("Providência") as HTMLInputElement).value).toBe("Objetivo inicial");
});
