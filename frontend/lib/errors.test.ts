import { expect, test } from "vitest";
import { humanError, mniErrorMessage } from "./errors";

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
// sua string e todas significam a mesma coisa: o servidor nao respondeu.
test.each([
  "Failed to fetch",
  "NetworkError when attempting to fetch resource.",
  "Load failed",
  "fetch failed",
  "The Internet connection appears to be offline."
])("falha de rede (%s) vira frase de servidor indisponivel", (raw) => {
  expect(humanError(new Error(raw), FALLBACK)).toBe(
    "Sem conexão com o servidor do Causor. Verifique sua internet e tente novamente."
  );
});

test("falha de rede ignora caixa e espacos", () => {
  expect(humanError(new Error("  failed to FETCH  "), FALLBACK)).toBe(
    "Sem conexão com o servidor do Causor. Verifique sua internet e tente novamente."
  );
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
