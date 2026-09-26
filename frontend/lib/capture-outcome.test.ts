import { expect, it } from "vitest";
import { captureFailureMessage } from "./capture-outcome";

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
