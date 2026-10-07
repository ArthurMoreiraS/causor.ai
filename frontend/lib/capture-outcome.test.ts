import { expect, it } from "vitest";
import { captureEmptyMessage, captureFailureMessage } from "./capture-outcome";

it("não apresenta DJEN 403 como captura concluída nem expõe URL com OAB", () => {
  const message = captureFailureMessage({
    intimacoes_novas: 0, processos_enriquecidos: 0, prazos_registrados: 0,
    djen_indisponivel: true,
    djen_erro: "Client error '403 Forbidden' for url 'https://cnj.example?numeroOab=123456'"
  });
  expect(message).toContain("HTTP 403");
  expect(message).toContain("Nenhuma intimação foi confirmada");
  expect(message).not.toContain("123456");
});

it("distingue dados parciais de uma captura completa", () => {
  expect(captureFailureMessage({
    intimacoes_novas: 2, processos_enriquecidos: 0, prazos_registrados: 0,
    djen_indisponivel: true, djen_erro: "DJEN HTTP 503"
  })).toContain("2 intimação(ões) foram salvas parcialmente");
  expect(captureFailureMessage({
    intimacoes_novas: 0, processos_enriquecidos: 0, prazos_registrados: 0
  })).toBeNull();
});

it("captura sem publicações no DJEN sugere as UFs da inscrição", () => {
  const base = { intimacoes_novas: 0, processos_enriquecidos: 0, prazos_registrados: 0 };
  const message = captureEmptyMessage({ ...base, publicacoes_encontradas: 0, ufs_sugeridas: ["DF", "SC"] }, "68703", "SP");
  expect(message).toContain("não tem publicações para a OAB 68703/SP");
  expect(message).toContain("DF, SC");
  expect(captureEmptyMessage({ ...base, publicacoes_encontradas: 0 }, "68703", "SP")).toContain("Confira o número e a UF");
});

it("não trata como vazia captura com publicações já conhecidas ou resultado antigo", () => {
  const base = { intimacoes_novas: 0, processos_enriquecidos: 0, prazos_registrados: 0 };
  expect(captureEmptyMessage({ ...base, publicacoes_encontradas: 4 }, "1", "DF")).toBeNull();
  expect(captureEmptyMessage(base, "1", "DF")).toBeNull();
});
