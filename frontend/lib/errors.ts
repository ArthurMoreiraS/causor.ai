// Traducao de erro tecnico para frase que o advogado entende. Corpo JSON cru,
// string vazia ou jargao de rede do navegador nao ajudam ninguem: viram uma
// frase humana e o detalhe fica no console.

// O browser entrega a MESMA falha ("Failed to fetch") em dois casos muito
// diferentes: a internet caiu, ou o servidor respondeu erro sem cabecalho
// CORS. Nao da para distinguir do lado do cliente, entao a frase nao pode
// afirmar so uma das causas — mandar o advogado reiniciar o roteador enquanto
// o servidor esta quebrado custa tempo e confianca.
export const UNREACHABLE =
  "Não foi possível falar com o servidor do Causor. Verifique sua conexão — se ela estiver boa, o servidor está fora do ar.";

// 500 tratado do backend (`InternalErrorToJsonMiddleware`). O advogado precisa
// saber que a falha nao e' dele nem dos dados que digitou.
const SERVER_FAULT =
  "O servidor do Causor falhou ao processar esta ação. Tente de novo; se repetir, avise o suporte.";

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
    "A listagem do tribunal veio incompleta. O Causor não usa autos parciais para gerar minuta.",
  tribunal_sem_mni:
    "Esse tribunal não atende por credencial oficial (MNI). A leitura dele roda pelo agente local: " +
    "o advogado entra no portal com o login dele (OAB e senha) e a sessão fica no computador dele."
};

export function mniErrorMessage(code: string | null | undefined): string {
  if (!code) return "O teste falhou. Confira os dados do credenciamento.";
  return MNI_MESSAGES[code] ?? `O teste falhou (${code}). Confira os dados do credenciamento.`;
}

// Codigo canonico dentro do corpo JSON de erro do backend.
function bodyErrorCode(raw: string): string | null {
  try {
    const parsed = JSON.parse(raw) as { detail?: { code?: unknown } | unknown };
    const detail = (parsed as { detail?: unknown }).detail;
    if (detail && typeof detail === "object" && "code" in detail) {
      const code = (detail as { code?: unknown }).code;
      return typeof code === "string" ? code : null;
    }
  } catch {
    return null;
  }
  return null;
}

export function humanError(err: unknown, fallback: string): string {
  const raw = err instanceof Error ? err.message.trim() : "";
  if (!raw) return fallback;
  const normalized = raw.toLowerCase();
  if (NETWORK_MARKERS.some((marker) => normalized.includes(marker))) return UNREACHABLE;
  if (raw.startsWith("{") || raw.startsWith("[")) {
    const code = bodyErrorCode(raw);
    if (code === "internal_error") return SERVER_FAULT;
    // Erro de domínio com código canônico e mensagem própria: dizer o que
    // fazer vale mais que o fallback genérico da tela.
    if (code && MNI_MESSAGES[code]) return MNI_MESSAGES[code];
    return fallback;
  }
  return raw;
}
