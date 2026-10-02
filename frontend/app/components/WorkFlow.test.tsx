// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { listarDocumentos } from "@/lib/api";
import { buscarFontesTrabalho, conferirEvidencias, criarPendenciaTrabalho, consultarOperacaoAtual, iniciarOperacaoTrabalho, type Trabalho } from "@/lib/work-api";
import { listarPacotes, listarTentativas, iniciarEnvioExterno, baixarArquivoTrabalho, conferirComprovante, type Pacote } from "@/lib/package-api";
import WorkEvidence from "./WorkEvidence";
import WorkProtocol from "./WorkProtocol";

vi.mock("@/lib/api", () => ({ listarDocumentos: vi.fn() }));
vi.mock("./DocumentEvidenceDialog", () => ({ default: () => <div>Fonte original</div> }));
vi.mock("@/lib/work-api", () => ({ conferirEvidencias: vi.fn(), criarPendenciaTrabalho: vi.fn(), iniciarOperacaoTrabalho: vi.fn(),
  consultarOperacaoAtual: vi.fn(), consultarOperacaoTrabalho: vi.fn(), obterTrabalhoAposOperacao: vi.fn(), buscarFontesTrabalho: vi.fn() }));
vi.mock("@/lib/package-api", () => ({ listarPacotes: vi.fn(), listarTentativas: vi.fn(), iniciarEnvioExterno: vi.fn(), baixarArquivoTrabalho: vi.fn(), conferirComprovante: vi.fn(), aprovarPacote: vi.fn(), cancelarTentativa: vi.fn(), criarPacote: vi.fn(), informarEnvio: vi.fn(), receberComprovante: vi.fn() }));

const work: Trabalho = { id: 1, processo_id: 2, intimacao_id: null, prazo_id: null, peticao_id: 3, responsavel_id: null,
  providencia: "Manifestação", instrucoes: "", grau: "2", polo: "Autor", versao: 7, created_at: "", updated_at: "",
  escopo: { data_referencia: "2026-09-20", declaracao: "Autos enviados para teste", documentos: [] },
  evidencias: { citations: [], analise: { fatos: [], cronologia: [], contradicoes: [], lacunas: ["Comprovante ausente"] },
    conferida: false, avisos: [], source_fingerprint: "abc", preparada_em: "", perguntas: [] } };
const package_: Pacote = { id: 8, trabalho_id: 1, peticao_id: 3, versao: 1, fingerprint: "a".repeat(64), atual: true,
  motivo: null, aprovada_em: "2026-09-20T12:00:00Z", destino: { tribunal: "TJSP", grau: "2", orgao: "Câmara", tipo_ato: "Manifestação", numero_processo: "0000123-45.2026.8.26.0100" },
  items: [{ nome: "01-peticao.pdf", tipo: "peticao", sha256: "b".repeat(64), size_bytes: 200 }] };

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listarDocumentos).mockResolvedValue({ total: 0, items: [] });
  vi.mocked(listarPacotes).mockResolvedValue({ items: [package_] });
  vi.mocked(listarTentativas).mockResolvedValue({ items: [] });
  vi.mocked(consultarOperacaoAtual).mockResolvedValue(null);
});

it("exige conferência explícita e envia a versão exata do trabalho", async () => {
  const saved = vi.fn();
  vi.mocked(conferirEvidencias).mockResolvedValue({ ...work, versao: 8 });
  render(<WorkEvidence work={work} disabled={false} onSaved={saved} onOpenDraft={vi.fn()} />);
  const review = screen.getByRole("button", { name: "Registrar conferência" }) as HTMLButtonElement;
  expect(review.disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Gerar nova versão da minuta" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText("Conferi as fontes, os pontos contrários e as lacunas desta análise."));
  fireEvent.click(review);
  await waitFor(() => expect(saved).toHaveBeenCalled());
  expect(conferirEvidencias).toHaveBeenCalledWith(work);
  expect(iniciarOperacaoTrabalho).not.toHaveBeenCalled();
});

it("transforma lacuna em tarefa vinculada ao trabalho", async () => {
  vi.mocked(criarPendenciaTrabalho).mockResolvedValue({ id: 9, status: "aberta" });
  render(<WorkEvidence work={work} disabled={false} onSaved={vi.fn()} onOpenDraft={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Criar pendência documental" }));
  await screen.findByText(/Pendência #9 vinculada/);
  expect(criarPendenciaTrabalho).toHaveBeenCalledWith(work, 0);
});

it("bloqueia redação quando uma evidência previamente conferida ficou desatualizada", () => {
  render(<WorkEvidence work={{ ...work, evidencias: { ...work.evidencias!, conferida: true }, evidencias_atuais: false, motivo_revisao: "Documentos mudaram" }} disabled={false} onSaved={vi.fn()} onOpenDraft={vi.fn()} />);
  expect(screen.getByRole("alert").textContent).toContain("Revisão necessária");
  expect((screen.getByRole("button", { name: "Gerar nova versão da minuta" }) as HTMLButtonElement).disabled).toBe(true);
});

it("invalida a marcação de conferência quando muda o inventário analisado", async () => {
  const onSaved = vi.fn();
  const { rerender } = render(<WorkEvidence work={work} disabled={false} onSaved={onSaved} onOpenDraft={vi.fn()} />);
  const checkbox = screen.getByLabelText("Conferi as fontes, os pontos contrários e as lacunas desta análise.") as HTMLInputElement;
  fireEvent.click(checkbox);
  expect(checkbox.checked).toBe(true);
  rerender(<WorkEvidence work={{ ...work, evidencias: { ...work.evidencias!, inventario: [{ documento_id: 10, documento_arquivo_id: 11, nome: "Autos", paginas: 5, extraction_status: "complete" }] } }} disabled={false} onSaved={onSaved} onOpenDraft={vi.fn()} />);
  await waitFor(() => expect(checkbox.checked).toBe(false));
  expect((screen.getByRole("button", { name: "Registrar conferência" }) as HTMLButtonElement).disabled).toBe(true);
});

it("ignora busca antiga após mudar a consulta", async () => {
  let finish!: (value: Awaited<ReturnType<typeof buscarFontesTrabalho>>) => void;
  vi.mocked(buscarFontesTrabalho).mockReturnValue(new Promise(resolve => { finish = resolve; }));
  render(<WorkEvidence work={work} disabled={false} onSaved={vi.fn()} onOpenDraft={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Buscar no texto original"), { target: { value: "pagamento" } });
  fireEvent.click(screen.getByRole("button", { name: "Buscar fontes" }));
  fireEvent.change(screen.getByLabelText("Buscar no texto original"), { target: { value: "contrato" } });
  await act(async () => finish({ items: [{ documento_id: 3, documento_arquivo_id: 4, chunk_id: 5, pagina: 1, quote: "Resultado antigo" }] }));
  expect(screen.queryByText("Resultado antigo")).toBeNull();
});

it("mantém fontes fixadas entre consultas e exige nova análise para conferir", async () => {
  vi.mocked(buscarFontesTrabalho).mockResolvedValue({ items: [{ documento_id: 3, documento_arquivo_id: 4, chunk_id: 5, pagina: 1, quote: "Comprovante", nome: "Autos" }] });
  const reviewed = { ...work, evidencias: { ...work.evidencias!, conferida: true } };
  render(<WorkEvidence work={reviewed} disabled={false} onSaved={vi.fn()} onOpenDraft={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Buscar no texto original"), { target: { value: "comprovante" } });
  fireEvent.click(screen.getByRole("button", { name: "Buscar fontes" }));
  await screen.findByText("Comprovante");
  fireEvent.click(screen.getByLabelText("Usar esta fonte na análise"));
  fireEvent.change(screen.getByLabelText("Buscar no texto original"), { target: { value: "contrato" } });
  expect(screen.getByText(/Fontes fixadas para a análise \(1\)/)).toBeTruthy();
  expect((screen.getByRole("button", { name: "Gerar nova versão da minuta" }) as HTMLButtonElement).disabled).toBe(true);
  vi.mocked(iniciarOperacaoTrabalho).mockResolvedValue({ id: 7, trabalho_id: reviewed.id, acao: "analise", versao: reviewed.versao,
    request_id: "r", request_ids: ["r"], status: "queued", resultado: null, erro: null, created_at: null });
  fireEvent.click(screen.getByRole("button", { name: "Atualizar análise das evidências" }));
  await waitFor(() => expect(iniciarOperacaoTrabalho).toHaveBeenCalledWith(reviewed, "analise", expect.any(String), [], [5]));
});

it("preserva perguntas e fontes editadas enquanto a análise termina", async () => {
  vi.mocked(buscarFontesTrabalho).mockResolvedValue({ items: [{ documento_id: 3, documento_arquivo_id: 4,
    chunk_id: 5, pagina: 1, quote: "Comprovante", nome: "Autos" }] });
  vi.mocked(iniciarOperacaoTrabalho).mockResolvedValue({ id: 7, trabalho_id: work.id, acao: "analise", versao: work.versao,
    request_id: "r", request_ids: ["r"], status: "queued", resultado: null, erro: null, created_at: null });
  const { rerender } = render(<WorkEvidence work={work} disabled={false} onSaved={vi.fn()} onOpenDraft={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Buscar no texto original"), { target: { value: "comprovante" } });
  fireEvent.click(screen.getByRole("button", { name: "Buscar fontes" }));
  await screen.findByText("Comprovante");
  fireEvent.click(screen.getByLabelText("Usar esta fonte na análise"));
  fireEvent.click(screen.getByRole("button", { name: "Atualizar análise das evidências" }));
  await waitFor(() => expect(iniciarOperacaoTrabalho).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText("Pontos que precisam ser respondidos"), { target: { value: "Pergunta nova" } });
  rerender(<WorkEvidence work={{ ...work, versao: 8,
    evidencias: { ...work.evidencias!, preparada_em: "2026-10-01T12:00:00Z" } }}
    disabled={false} onSaved={vi.fn()} onOpenDraft={vi.fn()} />);
  expect((screen.getByLabelText("Pontos que precisam ser respondidos") as HTMLTextAreaElement).value).toBe("Pergunta nova");
  expect(screen.getByText(/Fontes fixadas para a análise \(1\)/)).toBeTruthy();
});

it("invalida a conferência se a análise muda com as mesmas fontes e preserva campos sujos", async () => {
  vi.mocked(buscarFontesTrabalho).mockResolvedValue({ items: [{ documento_id: 3, documento_arquivo_id: 4,
    chunk_id: 5, pagina: 1, quote: "Comprovante", nome: "Autos" }] });
  const { rerender } = render(<WorkEvidence work={work} disabled={false} onSaved={vi.fn()} onOpenDraft={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Buscar no texto original"), { target: { value: "comprovante" } });
  fireEvent.click(screen.getByRole("button", { name: "Buscar fontes" }));
  await screen.findByText("Comprovante");
  fireEvent.click(screen.getByLabelText("Usar esta fonte na análise"));
  fireEvent.change(screen.getByLabelText("Pontos que precisam ser respondidos"), { target: { value: "Pergunta local" } });
  const checkbox = screen.getByLabelText("Conferi as fontes, os pontos contrários e as lacunas desta análise.") as HTMLInputElement;
  fireEvent.click(checkbox);
  expect(checkbox.checked).toBe(true);
  rerender(<WorkEvidence work={{ ...work, versao: 8,
    evidencias: { ...work.evidencias!, preparada_em: "2026-10-02T09:00:00Z",
      analise: { ...work.evidencias!.analise, lacunas: ["Outra lacuna"] } } }}
    disabled={false} onSaved={vi.fn()} onOpenDraft={vi.fn()} />);
  await waitFor(() => expect(checkbox.checked).toBe(false));
  expect((screen.getByLabelText("Pontos que precisam ser respondidos") as HTMLTextAreaElement).value).toBe("Pergunta local");
  expect(screen.getByText(/Fontes fixadas para a análise \(1\)/)).toBeTruthy();
});

it("descarta busca atrasada e conferência ao mudar o snapshot, preservando perguntas", async () => {
  let finish!: (value: Awaited<ReturnType<typeof buscarFontesTrabalho>>) => void;
  vi.mocked(buscarFontesTrabalho).mockReturnValue(new Promise(resolve => { finish = resolve; }));
  const { rerender } = render(<WorkEvidence work={work} disabled={false} onSaved={vi.fn()} onOpenDraft={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Pontos que precisam ser respondidos"), { target: { value: "Qual pagamento?" } });
  fireEvent.click(screen.getByLabelText("Conferi as fontes, os pontos contrários e as lacunas desta análise."));
  fireEvent.change(screen.getByLabelText("Buscar no texto original"), { target: { value: "pagamento" } });
  fireEvent.click(screen.getByRole("button", { name: "Buscar fontes" }));
  rerender(<WorkEvidence work={{ ...work, versao: 8, evidencias: { ...work.evidencias!, source_fingerprint: "novo" } }} disabled={false} onSaved={vi.fn()} onOpenDraft={vi.fn()} />);
  await act(async () => finish({ items: [{ documento_id: 3, documento_arquivo_id: 4, chunk_id: 5, pagina: 1, quote: "Busca antiga" }] }));
  expect(screen.queryByText("Busca antiga")).toBeNull();
  expect((screen.getByLabelText("Pontos que precisam ser respondidos") as HTMLTextAreaElement).value).toBe("Qual pagamento?");
  expect((screen.getByLabelText("Conferi as fontes, os pontos contrários e as lacunas desta análise.") as HTMLInputElement).checked).toBe(false);
  expect(screen.getByText(/Suas perguntas foram preservadas/)).toBeTruthy();
  expect((screen.getByRole("button", { name: "Buscar fontes" }) as HTMLButtonElement).disabled).toBe(false);
});

it("não publica resposta de outro trabalho mesmo quando o componente é reutilizado", async () => {
  let finish!: (value: Awaited<ReturnType<typeof buscarFontesTrabalho>>) => void;
  vi.mocked(buscarFontesTrabalho).mockReturnValue(new Promise(resolve => { finish = resolve; }));
  const saved = vi.fn();
  const { rerender } = render(<WorkEvidence work={work} disabled={false} onSaved={saved} onOpenDraft={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Buscar no texto original"), { target: { value: "antigo" } });
  fireEvent.click(screen.getByRole("button", { name: "Buscar fontes" }));
  rerender(<WorkEvidence work={{ ...work, id: 2, versao: 1 }} disabled={false} onSaved={saved} onOpenDraft={vi.fn()} />);
  await act(async () => finish({ items: [{ documento_id: 3, documento_arquivo_id: 4, chunk_id: 5, pagina: 1, quote: "Outro trabalho" }] }));
  expect(screen.queryByText("Outro trabalho")).toBeNull();
  expect((screen.getByLabelText("Buscar no texto original") as HTMLInputElement).value).toBe("");
});

it("baixar pacote aprovado não cria tentativa nem confirma envio", async () => {
  render(<WorkProtocol work={work} disabled={false} onChanged={vi.fn()} />);
  fireEvent.click(await screen.findByRole("button", { name: "Baixar pacote aprovado" }));
  await waitFor(() => expect(baixarArquivoTrabalho).toHaveBeenCalledWith("/pacotes/8/exportar", "pacote-8.zip"));
  expect(iniciarEnvioExterno).not.toHaveBeenCalled();
  expect(conferirComprovante).not.toHaveBeenCalled();
});

it("comprovante divergente bloqueia confirmação mesmo após marcar a conferência", async () => {
  vi.mocked(listarTentativas).mockResolvedValue({ items: [{ id: 4, pacote_id: 8, canal: "externo", status: "envio_informado", versao: 3,
    dados: null, comprovantes: [{ id: 10, nome: "outro.pdf", sha256: "c", status: "divergente", dados: { numeros_extraidos: ["outro"], texto_disponivel: true } }] }] });
  render(<WorkProtocol work={work} disabled={false} onChanged={vi.fn()} />);
  await screen.findByText(/Número do processo divergente/);
  fireEvent.change(screen.getByLabelText("Número do protocolo informado"), { target: { value: "TESTE-123" } });
  fireEvent.change(screen.getByLabelText("Data e hora do ato"), { target: { value: "2026-09-20T12:00" } });
  fireEvent.change(screen.getByLabelText("Observações da conferência"), { target: { value: "Conferi visualmente os dados do arquivo" } });
  fireEvent.click(screen.getByLabelText("Conferi processo, destino, número, data do ato e correspondência com os arquivos aprovados."));
  const button = screen.getByRole("button", { name: "Registrar conferência humana do comprovante" }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  fireEvent.click(button);
  expect(conferirComprovante).not.toHaveBeenCalled();
});
