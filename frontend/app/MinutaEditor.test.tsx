// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { baixarFonteCitada, type Peticao } from "@/lib/api";
import MinutaEditor from "./MinutaEditor";

vi.mock("@/lib/api", () => ({ baixarFonteCitada: vi.fn(), baixarPeticaoPdf: vi.fn() }));
const draft = { id: 8, processo_id: 2, tipo: "Manifestação", conteudo: "Texto salvo", status: "rascunho", dossie: null } as Peticao;
const props = () => ({ peticao: draft, processo: null, prazo: null, busy: false, onSave: vi.fn().mockResolvedValue(true), onClose: vi.fn() });
afterEach(cleanup);
beforeEach(() => vi.clearAllMocks());

it("mantém a edição ao fechar e só descarta após escolha explícita", () => {
  const p = props(); render(<MinutaEditor {...p} />);
  fireEvent.change(screen.getByRole("textbox", { name: "Conteúdo da minuta" }), { target: { value: "Texto alterado" } });
  fireEvent.click(screen.getByRole("button", { name: "Fechar revisão" }));
  expect(p.onClose).not.toHaveBeenCalled();
  expect(screen.getByText("Você tem alterações não salvas.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Continuar editando" }));
  expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("Texto alterado");
  fireEvent.keyDown(document, { key: "Escape" });
  fireEvent.click(screen.getByRole("button", { name: "Descartar e sair" }));
  expect(p.onClose).toHaveBeenCalledOnce();
});

it("salvar e sair só fecha depois da confirmação de sucesso", async () => {
  const p = props(); p.onSave.mockResolvedValueOnce(false).mockResolvedValueOnce(true);
  render(<MinutaEditor {...p} />);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Minha revisão" } });
  fireEvent.click(screen.getByRole("button", { name: "Fechar revisão" }));
  fireEvent.click(screen.getByRole("button", { name: "Salvar e sair" }));
  await screen.findByText("Não foi possível salvar. Sua edição continua aberta.");
  expect(p.onClose).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Salvar e sair" }));
  await waitFor(() => expect(p.onClose).toHaveBeenCalledOnce());
  expect(p.onSave).toHaveBeenLastCalledWith("Minha revisão");
});

it("protege a saída do navegador enquanto há alterações", () => {
  render(<MinutaEditor {...props()} />);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Alteração" } });
  const event = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(event);
  expect(event.defaultPrevented).toBe(true);
});

it("abre a versão citada ao lado sem descartar o texto em edição", async () => {
  vi.stubGlobal("URL", class extends URL { static createObjectURL = vi.fn(() => "blob:fonte"); static revokeObjectURL = vi.fn(); });
  vi.mocked(baixarFonteCitada).mockResolvedValue(new Blob(["pdf"]));
  const p = props();
  render(<MinutaEditor {...p} peticao={{ ...draft, dossie: { citations: [{ documento_id: 7, documento_arquivo_id: 9, pagina: 4, quote: "Fonte", chunk_id: 2 }] } } as Peticao} />);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Revisão em andamento" } });
  fireEvent.click(screen.getByRole("button", { name: /DOC-7.*página 4/ }));
  await screen.findByTitle("Documento citado");
  expect(baixarFonteCitada).toHaveBeenCalledWith(7, 9);
  expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("Revisão em andamento");
  expect(p.onClose).not.toHaveBeenCalled();
  vi.unstubAllGlobals();
});
