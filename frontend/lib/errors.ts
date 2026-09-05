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

// Gate fail-closed do contexto (`autos/context.py`): a minuta so nasce dos
// autos reais. E' o comportamento mais importante do produto e chegava ao
// advogado como erro generico — ele via "A acao nao foi concluida" sem saber
// que faltavam os autos nem o que fazer.
export const GATE_CONTEXTO_CODE = "process_context_incomplete";

const GATE_CONTEXTO_MESSAGE =
  "Os autos deste processo ainda não estão completos. O Causor não escreve minuta " +
  "sobre processo pela metade — vamos buscar as peças que faltam.";

/** Passo acionavel que o backend devolve junto do 409 do gate. */
export type GateContexto = {
  processo_id: number;
  missing: string[];
  next_step: string | null;
};

/** Devolve o payload do gate quando o erro e' o bloqueio de contexto; senao `null`.
 *
 * E' o que permite a tela abrir o assistente no lugar de so mostrar um toast:
 * o backend ja manda `processo_id` e `next_step` mastigados. */
export function gateContexto(err: unknown): GateContexto | null {
  const raw = err instanceof Error ? err.message.trim() : "";
  if (!raw.startsWith("{")) return null;
  try {
    const parsed = JSON.parse(raw) as {
      detail?: {
        code?: unknown;
        processo_id?: unknown;
        missing?: unknown;
        next_step?: unknown;
      };
    };
    const detail = parsed.detail;
    if (!detail || detail.code !== GATE_CONTEXTO_CODE) return null;
    if (typeof detail.processo_id !== "number") return null;
    return {
      processo_id: detail.processo_id,
      missing: Array.isArray(detail.missing) ? (detail.missing as string[]) : [],
      next_step: typeof detail.next_step === "string" ? detail.next_step : null
    };
  } catch {
    return null;
  }
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
    if (code === GATE_CONTEXTO_CODE) return GATE_CONTEXTO_MESSAGE;
    if (code === "draft_context_budget_exceeded") {
      return "O conteúdo necessário para esta minuta excede a capacidade configurada. " +
        "Os autos foram preservados. Solicite um ajuste de capacidade ao responsável pelo Causor.";
    }
    // Erro de domínio com código canônico e mensagem própria: dizer o que
    // fazer vale mais que o fallback genérico da tela.
    if (code && MNI_MESSAGES[code]) return MNI_MESSAGES[code];
    return fallback;
  }
  return raw;
}
