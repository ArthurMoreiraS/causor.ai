import type { CaptureResult } from "./api";

export function captureFailureMessage(result: CaptureResult): string | null {
  if (!result.djen_indisponivel) return null;
  const source = result.djen_erro?.includes("403")
    ? "O DJEN recusou a consulta (HTTP 403). É necessário verificar o acesso do servidor à API do CNJ."
    : "A consulta ao DJEN foi interrompida. Tente novamente após a fonte se recuperar.";
  const partial = result.intimacoes_novas > 0
    ? ` ${result.intimacoes_novas} intimação(ões) foram salvas parcialmente.`
    : " Nenhuma intimação foi confirmada.";
  return `A OAB foi cadastrada, mas a captura não foi concluída. ${source}${partial}`;
}
