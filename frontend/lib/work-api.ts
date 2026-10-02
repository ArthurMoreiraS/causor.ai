import { controlRequest, request, type Pagina, type Processo } from "./api";

export type FonteTrabalho = { documento_id: number; documento_arquivo_id: number; chunk_id: number; pagina: number; quote: string; nome?: string; sha256?: string; fixada?: boolean };
export type FatoTrabalho = { texto: string; fontes: number[]; natureza: string };
export type EvidenciasTrabalho = { citations: FonteTrabalho[]; inventario?: { documento_id: number; documento_arquivo_id: number; nome: string | null; paginas: number | null; extraction_status: string }[]; analise: { fatos: FatoTrabalho[]; cronologia: FatoTrabalho[]; contradicoes: FatoTrabalho[]; lacunas: string[] };
  conferida: boolean; avisos: string[]; source_fingerprint: string; preparada_em: string; perguntas: string[] };
export type PecaIndice = { nome: string; pagina_inicio: number; pagina_fim: number };
export type DocumentoEscopo = { versao_id: number; origem: "autos_enviados" | "subsidio_cliente" | "fonte_externa"; pecas: PecaIndice[] };
export type EscopoTrabalho = { data_referencia: string; declaracao: string; documentos: DocumentoEscopo[] };
export type Trabalho = {
  evidencias_atuais?: boolean | null; motivo_revisao?: string | null;
  id: number; processo_id: number | null; intimacao_id: number | null; prazo_id: number | null;
  peticao_id: number | null; responsavel_id: number | null; providencia: string; instrucoes: string;
  grau: string; polo: string | null; versao: number; escopo: EscopoTrabalho | null;
  evidencias: EvidenciasTrabalho | null; created_at: string; updated_at: string;
};
export type TrabalhoInput = { processo_id: number; providencia: string; instrucoes: string; grau: "1" | "2"; polo?: string | null; intimacao_id?: number; prazo_id?: number };
export type OperacaoTrabalho = { id: number; trabalho_id: number; acao: "analise" | "minuta"; versao: number;
  request_id: string; request_ids: string[]; status: "queued" | "running" | "completed" | "failed";
  resultado: { trabalho_id: number; versao: number; peticao_id: number | null } | null;
  erro: string | null; created_at: string | null };
function operationRequest<T>(path: string, init?: RequestInit): Promise<T> {
  return controlRequest<T>(path, init, 12000).catch((error: unknown) => {
    if (error instanceof Error && error.message.includes("Verifique a captura novamente"))
      throw new Error("Tempo de resposta excedido. Consulte a operação novamente.");
    throw error;
  });
}
export function iniciarOperacaoTrabalho(work: Trabalho, acao: "analise" | "minuta", requestId: string,
                                       perguntas: string[] = [], fontesFixadas: number[] = []): Promise<OperacaoTrabalho> {
  return operationRequest(`/trabalhos/${work.id}/operacoes`, { method: "POST", body: JSON.stringify({
    versao: work.versao, acao, request_id: requestId, perguntas, fontes_fixadas: fontesFixadas }) });
}
export function consultarOperacaoTrabalho(workId: number, jobId: number): Promise<OperacaoTrabalho> {
  return operationRequest(`/trabalhos/${workId}/operacoes/${jobId}`);
}
export function consultarOperacaoAtual(workId: number): Promise<OperacaoTrabalho | null> {
  return operationRequest(`/trabalhos/${workId}/operacoes/atual`);
}
export function obterTrabalhoAposOperacao(workId: number): Promise<Trabalho> {
  return operationRequest(`/trabalhos/${workId}`);
}
export function criarProcesso(payload: { numero: string; tribunal?: string; cliente_id?: number }): Promise<Processo> {
  return request("/processos", { method: "POST", body: JSON.stringify(payload) });
}
export function listarTrabalhos(processoId?: number, offset = 0): Promise<Pagina<Trabalho>> {
  return request(`/trabalhos?limit=50&offset=${offset}${processoId ? `&processo_id=${processoId}` : ""}`);
}
export function obterTrabalho(id: number): Promise<Trabalho> { return request(`/trabalhos/${id}`); }
export function criarTrabalho(payload: TrabalhoInput): Promise<Trabalho> {
  return request("/trabalhos", { method: "POST", body: JSON.stringify(payload) });
}
export function atualizarTrabalho(id: number, payload: Partial<Omit<TrabalhoInput, "processo_id">> & { versao: number }): Promise<Trabalho> {
  return request(`/trabalhos/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}
export function prepararEvidencias(work: Trabalho, perguntas: string[], fontes_fixadas: number[]): Promise<Trabalho> {
  return request(`/trabalhos/${work.id}/evidencias`, { method: "POST", body: JSON.stringify({ versao: work.versao, perguntas, fontes_fixadas }) });
}
export function conferirEvidencias(work: Trabalho): Promise<Trabalho> {
  return request(`/trabalhos/${work.id}/evidencias/conferir`, { method: "POST", body: JSON.stringify({ versao: work.versao }) });
}
export function gerarMinutaTrabalho(work: Trabalho): Promise<Trabalho> {
  return request(`/trabalhos/${work.id}/minuta`, { method: "POST", body: JSON.stringify({ versao: work.versao }) });
}
export function salvarEscopo(work: Trabalho, scope: EscopoTrabalho): Promise<Trabalho> {
  return request(`/trabalhos/${work.id}/escopo`, { method: "PUT", body: JSON.stringify({ ...scope, versao: work.versao }) });
}
export function buscarFontesTrabalho(work: Trabalho, q: string): Promise<{ items: FonteTrabalho[] }> {
  return request(`/trabalhos/${work.id}/fontes?q=${encodeURIComponent(q)}`);
}
export function criarPendenciaTrabalho(work: Trabalho, index: number): Promise<{ id: number; status: string }> {
  return request(`/trabalhos/${work.id}/lacunas/${index}/tarefa`, { method: "POST", body: JSON.stringify({ versao: work.versao }) });
}
