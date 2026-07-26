// Traducao de erro tecnico para frase que o advogado entende. Corpo JSON cru,
// string vazia ou jargao de rede do navegador nao ajudam ninguem: viram uma
// frase humana e o detalhe fica no console.

const OFFLINE =
  "Sem conexão com o servidor do Causor. Verifique sua internet e tente novamente.";

// Cada engine tem a sua string para "o fetch nao chegou no servidor".
const NETWORK_MARKERS = [
  "failed to fetch",
  "networkerror",
  "load failed",
  "fetch failed",
  "connection appears to be offline"
];

// Codigos canonicos de connectors/errors.py. O advogado precisa saber o que
// fazer a seguir, nao o nome interno da excecao.
const MNI_MESSAGES: Record<string, string> = {
  access_denied:
    "O tribunal recusou a credencial. Confira o id consultante e a senha do credenciamento.",
  mni_unavailable:
    "O webservice do tribunal não respondeu. Pode ser instabilidade — tente de novo mais tarde.",
  layout_unknown:
    "O tribunal respondeu em formato inesperado. A leitura desse processo cai no computador do advogado.",
  document_download_failed:
    "O tribunal listou o processo mas não entregou o documento. A captura vai pelo computador do advogado.",
  cursor_incomplete:
    "A listagem do tribunal veio incompleta. O Causor não usa autos parciais para gerar minuta."
};

export function mniErrorMessage(code: string | null | undefined): string {
  if (!code) return "O teste falhou. Confira os dados do credenciamento.";
  return MNI_MESSAGES[code] ?? `O teste falhou (${code}). Confira os dados do credenciamento.`;
}

export function humanError(err: unknown, fallback: string): string {
  const raw = err instanceof Error ? err.message.trim() : "";
  if (!raw) return fallback;
  const normalized = raw.toLowerCase();
  if (NETWORK_MARKERS.some((marker) => normalized.includes(marker))) return OFFLINE;
  if (raw.startsWith("{") || raw.startsWith("[")) return fallback;
  return raw;
}
