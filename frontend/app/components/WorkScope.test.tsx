// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { listarDocumentos } from "@/lib/api";
import { salvarEscopo, type Trabalho } from "@/lib/work-api";
import WorkScope from "./WorkScope";

vi.mock("@/lib/api", () => ({ listarDocumentos: vi.fn() }));
vi.mock("@/lib/work-api", () => ({ salvarEscopo: vi.fn() }));
vi.mock("./DocumentEvidenceDialog", () => ({ default: () => null }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("preserva índice editado durante snapshot remoto e atualiza quando está limpo", async () => {
  vi.mocked(listarDocumentos).mockResolvedValue({ total: 0, items: [] });
  const work: Trabalho = { id: 1, processo_id: 2, intimacao_id: null, prazo_id: null,
    peticao_id: null, responsavel_id: null, providencia: "Manifestação", instrucoes: "", grau: "1",
    polo: "Autor", versao: 1, evidencias: null, created_at: "", updated_at: "",
    escopo: { data_referencia: "2026-09-20", declaracao: "Autos conferidos até esta data.", documentos: [] } };
  const onDirtyChange = vi.fn();
  const { rerender } = render(<WorkScope work={work} disabled={false} onSaved={vi.fn()} onDirtyChange={onDirtyChange} />);
  await waitFor(() => expect(onDirtyChange).toHaveBeenCalledWith(false));
  const cleanRemote = { ...work, versao: 2, escopo: { ...work.escopo!, declaracao: "Declaração remota inicial." } };
  rerender(<WorkScope work={cleanRemote} disabled={false} onSaved={vi.fn()} onDirtyChange={onDirtyChange} />);
  await waitFor(() => expect((screen.getByLabelText("Declaração de cobertura e limitações") as HTMLTextAreaElement).value).toBe("Declaração remota inicial."));
  fireEvent.change(screen.getByLabelText("Declaração de cobertura e limitações"), { target: { value: "Minha declaração ainda não salva." } });
  await waitFor(() => expect(onDirtyChange).toHaveBeenCalledWith(true));
  const remote = { ...work, versao: 3, escopo: { ...work.escopo!, declaracao: "Declaração remota alterada." } };
  rerender(<WorkScope work={remote} disabled={false} onSaved={vi.fn()} onDirtyChange={onDirtyChange} />);
  expect((screen.getByLabelText("Declaração de cobertura e limitações") as HTMLTextAreaElement).value).toBe("Minha declaração ainda não salva.");
  expect(screen.getByRole("alert").textContent).toContain("outra sessão");
});

it("ignora metadados do servidor ao calcular alterações e ao salvar", async () => {
  vi.mocked(listarDocumentos).mockResolvedValue({ total: 0, items: [] });
  const scope = { data_referencia: "2026-09-20", declaracao: "Autos conferidos até esta data.", documentos: [],
    origem: "advogado", usuario_id: 5, declarada_em: "2026-09-20T10:00:00Z" };
  const work: Trabalho = { id: 1, processo_id: 2, intimacao_id: null, prazo_id: null, peticao_id: null,
    responsavel_id: null, providencia: "Manifestação", instrucoes: "", grau: "1", polo: "Autor",
    versao: 1, escopo: scope, evidencias: null, created_at: "", updated_at: "" };
  const onDirtyChange = vi.fn();
  vi.mocked(salvarEscopo).mockResolvedValue({ ...work, versao: 2, escopo: { ...scope, declaracao: "Cobertura revisada pelo servidor." } });
  const { rerender } = render(<WorkScope work={work} disabled={false} onSaved={vi.fn()} onDirtyChange={onDirtyChange} />);
  await waitFor(() => expect(onDirtyChange).toHaveBeenLastCalledWith(false));
  fireEvent.change(screen.getByLabelText("Declaração de cobertura e limitações"), { target: { value: "Cobertura enviada para salvar." } });
  fireEvent.click(screen.getByRole("button", { name: "Registrar escopo e índice" }));
  await waitFor(() => expect(onDirtyChange).toHaveBeenLastCalledWith(false));
  rerender(<WorkScope work={{ ...work, versao: 2, escopo: { ...scope, declaracao: "Cobertura revisada pelo servidor." } }} disabled={false} onSaved={vi.fn()} onDirtyChange={onDirtyChange} />);
  expect((screen.getByLabelText("Declaração de cobertura e limitações") as HTMLTextAreaElement).value).toBe("Cobertura revisada pelo servidor.");
  expect(onDirtyChange).toHaveBeenLastCalledWith(false);
});

it("ignora resposta de salvar escopo depois que a versão do trabalho mudou", async () => {
  vi.mocked(listarDocumentos).mockResolvedValue({ total: 0, items: [] });
  let finish!: (work: Trabalho) => void;
  vi.mocked(salvarEscopo).mockReturnValue(new Promise(resolve => { finish = resolve; }));
  const work: Trabalho = { id: 1, processo_id: 2, intimacao_id: null, prazo_id: null, peticao_id: null,
    responsavel_id: null, providencia: "Manifestação", instrucoes: "", grau: "1", polo: "Autor", versao: 1,
    escopo: { data_referencia: "2026-09-20", declaracao: "Autos conferidos até esta data.", documentos: [] },
    evidencias: null, created_at: "", updated_at: "" };
  const saved = vi.fn();
  const { rerender } = render(<WorkScope work={work} disabled={false} onSaved={saved} />);
  fireEvent.click(screen.getByRole("button", { name: "Registrar escopo e índice" }));
  rerender(<WorkScope work={{ ...work, versao: 2 }} disabled={false} onSaved={saved} />);
  finish({ ...work, versao: 2 });
  await waitFor(() => expect((screen.getByRole("button", { name: "Registrar escopo e índice" }) as HTMLButtonElement).disabled).toBe(false));
  expect(saved).not.toHaveBeenCalled();
});
