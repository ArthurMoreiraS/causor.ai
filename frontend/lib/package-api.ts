import { request, resourceRequest } from "./api";
import type { Trabalho } from "./work-api";
export type DestinoPacote = { tribunal: string; grau: "1" | "2"; orgao: string; tipo_ato: string; sistema?: string | null; numero_processo?: string };
export type AnexoPacote = { versao_id: number; nome: string };
export type Pacote = { id: number; trabalho_id: number; peticao_id: number; versao: number; fingerprint: string;
  aprovada_em: string | null; atual: boolean; motivo: string | null; destino: DestinoPacote;
  items: { nome: string; tipo: string; sha256: string; size_bytes: number; versao_id?: number }[] };
export type Comprovante = { id: number; nome: string; sha256: string; status: string;
  dados: { numeros_extraidos: string[]; protocolos_sugeridos?: string[]; datas_sugeridas?: string[]; texto_disponivel: boolean; metodo?: string; conferencia?: { protocolo: string; data_ato: string } } };
export type Tentativa = { id: number; pacote_id: number; canal: string; status: string; versao: number;
  dados: { declaracao?: { protocolo: string; data_ato: string }; comprovante_id?: number } | null; comprovantes: Comprovante[] };
export function listarPacotes(work: Trabalho): Promise<{ items: Pacote[] }> { return request(`/trabalhos/${work.id}/pacotes`); }
export function criarPacote(work: Trabalho, destino: DestinoPacote, anexos: AnexoPacote[]): Promise<Pacote> {
  return request(`/trabalhos/${work.id}/pacotes`, { method: "POST", body: JSON.stringify({ versao_trabalho: work.versao, destino, anexos }) });
}
export function aprovarPacote(package_: Pacote): Promise<Pacote> {
  return request(`/pacotes/${package_.id}/aprovar`, { method: "POST", body: JSON.stringify({ fingerprint: package_.fingerprint }) });
}
export function listarTentativas(package_: Pacote): Promise<{ items: Tentativa[] }> { return request(`/pacotes/${package_.id}/tentativas`); }
export function iniciarEnvioExterno(package_: Pacote, key: string): Promise<Tentativa> {
  return request(`/pacotes/${package_.id}/tentativas`, { method: "POST", body: JSON.stringify({ fingerprint: package_.fingerprint, idempotency_key: key }) });
}
export function informarEnvio(attempt: Tentativa, protocolo: string, data_ato: string): Promise<Tentativa> {
  return request(`/tentativas/${attempt.id}/informar-envio`, { method: "POST", body: JSON.stringify({ versao: attempt.versao, protocolo, data_ato }) });
}
export function cancelarTentativa(attempt: Tentativa, motivo: string): Promise<Tentativa> {
  return request(`/tentativas/${attempt.id}/cancelar`, { method: "POST", body: JSON.stringify({ versao: attempt.versao, motivo }) });
}
export async function receberComprovante(attempt: Tentativa, file: File): Promise<Tentativa> {
  const body = new FormData(); body.append("arquivo", file);
  return (await resourceRequest(`/tentativas/${attempt.id}/comprovantes?versao=${attempt.versao}`, { method: "POST", body })).json();
}
export function conferirComprovante(attempt: Tentativa, receipt: Comprovante, data: { numero_processo: string; protocolo: string; data_ato: string; observacoes: string }): Promise<Tentativa> {
  return request(`/comprovantes/${receipt.id}/conferir`, { method: "POST", body: JSON.stringify({ ...data, versao: attempt.versao }) });
}
export async function baixarArquivoTrabalho(path: string, filename: string) {
  const blob = await (await resourceRequest(path)).blob();
  const url = URL.createObjectURL(blob), anchor = document.createElement("a");
  anchor.href = url; anchor.download = filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
