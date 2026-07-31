import { expect, test } from "vitest";
import { gateContexto, humanError, mniErrorMessage, UNREACHABLE } from "./errors";

const FALLBACK = "Falha ao carregar credenciais";

test("mensagem util do backend passa direto", () => {
  expect(humanError(new Error("Credencial revogada"), FALLBACK)).toBe("Credencial revogada");
});

test("corpo JSON cru vira a frase humana", () => {
  expect(humanError(new Error("{}"), FALLBACK)).toBe(FALLBACK);
  expect(humanError(new Error('{"detail":"x"}'), FALLBACK)).toBe(FALLBACK);
  expect(humanError(new Error("[1,2]"), FALLBACK)).toBe(FALLBACK);
});

test("erro vazio ou nao-Error vira a frase humana", () => {
  expect(humanError(new Error("   "), FALLBACK)).toBe(FALLBACK);
  expect(humanError("boom", FALLBACK)).toBe(FALLBACK);
  expect(humanError(null, FALLBACK)).toBe(FALLBACK);
});

// O advogado nunca deve ler jargao de rede do navegador. Cada engine tem a
// sua string e todas significam a mesma coisa: o fetch nao chegou ao servidor.
test.each([
  "Failed to fetch",
  "NetworkError when attempting to fetch resource.",
  "Load failed",
  "fetch failed",
  "The Internet connection appears to be offline."
])("falha de rede (%s) vira frase de servidor inalcancavel", (raw) => {
  expect(humanError(new Error(raw), FALLBACK)).toBe(UNREACHABLE);
});

test("falha de rede ignora caixa e espacos", () => {
  expect(humanError(new Error("  failed to FETCH  "), FALLBACK)).toBe(UNREACHABLE);
});

// O browser entrega `Failed to fetch` tanto quando a internet caiu quanto
// quando o servidor respondeu erro sem cabecalho CORS. Mandar o advogado
// conferir o wi-fi enquanto o servidor esta quebrado e' um diagnostico errado
// com custo real: ele reinicia o roteador em vez de avisar o suporte.
test("falha de rede nao culpa so a internet do advogado", () => {
  expect(UNREACHABLE).toMatch(/servidor/i);
  expect(UNREACHABLE).not.toMatch(/verifique sua internet e tente novamente\.$/i);
});

// O backend passou a devolver 500 como JSON com codigo canonico; o corpo cru
// nao diz ao advogado que o problema nao e' dele.
test("erro interno do servidor vira frase propria, nao o fallback generico", () => {
  const body = '{"detail":{"code":"internal_error"}}';
  const message = humanError(new Error(body), FALLBACK);
  expect(message).not.toBe(FALLBACK);
  expect(message).toMatch(/servidor/i);
});

// O botao "Testar" e a primeira coisa que o advogado clica depois do
// credenciamento; codigo canonico cru nao diz o que fazer a seguir.
test("codigo canonico do MNI vira diagnostico acionavel", () => {
  expect(mniErrorMessage("access_denied")).toMatch(/credenciamento/i);
  expect(mniErrorMessage("mni_unavailable")).toMatch(/tribunal/i);
  expect(mniErrorMessage("layout_unknown")).toMatch(/inesperad/i);
  expect(mniErrorMessage("document_download_failed")).toMatch(/documento/i);
  expect(mniErrorMessage("cursor_incomplete")).toMatch(/incompleta/i);
});

test("codigo desconhecido ou ausente ainda produz frase legivel", () => {
  expect(mniErrorMessage("codigo_novo_do_backend")).toBe(
    "O teste falhou (codigo_novo_do_backend). Confira os dados do credenciamento."
  );
  expect(mniErrorMessage(null)).toBe("O teste falhou. Confira os dados do credenciamento.");
  expect(mniErrorMessage(undefined)).toBe("O teste falhou. Confira os dados do credenciamento.");
});

// O gate de contexto e a peca mais importante do produto: a minuta so nasce
// dos autos reais. Ate 30/07 ele chegava ao advogado como "A acao nao foi
// concluida" — erro generico, sem dizer que faltam os autos e sem caminho.
test("gate de contexto vira frase que nomeia os autos", () => {
  const body =
    '{"detail":{"code":"process_context_incomplete","processo_id":12,' +
    '"missing":["1o grau"],"next_step":"pair_agent","rota":{"sistema":"EPROC"}}}';
  const message = humanError(new Error(body), FALLBACK);
  expect(message).not.toBe(FALLBACK);
  expect(message).toMatch(/autos/i);
});

test("gate de contexto entrega o processo e o proximo passo para a UI conduzir", () => {
  const body =
    '{"detail":{"code":"process_context_incomplete","processo_id":12,' +
    '"missing":["1o grau"],"next_step":"pair_agent","rota":{"sistema":"EPROC"}}}';

  expect(gateContexto(new Error(body))).toEqual({
    processo_id: 12,
    missing: ["1o grau"],
    next_step: "pair_agent"
  });
});

test("erro que nao e o gate nao aciona o assistente", () => {
  expect(gateContexto(new Error("Failed to fetch"))).toBeNull();
  expect(gateContexto(new Error('{"detail":{"code":"internal_error"}}'))).toBeNull();
  expect(gateContexto(null)).toBeNull();
});
