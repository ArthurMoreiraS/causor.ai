// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { IntimacaoRow } from "@/lib/views";
import IntimacoesView from "./IntimacoesView";

afterEach(cleanup);

function row(id: number, tipo: string, extra: Partial<IntimacaoRow> = {}, status?: string): IntimacaoRow {
  return {
    intimacao: { id, processo_id: null, fonte: "DJEN", numero_processo: null, tribunal: "TJSP",
      tipo_comunicacao: tipo, teor: "", data_disponibilizacao: "2026-10-01", data_publicacao: null,
      prazo_analise: status ? { status } : null },
    processo: null, prazo: null, peticao: null, ...extra
  };
}

const prazo = (id: number, data_fatal: string, revisao_status = "calculado_a_revisar") => ({
  id, processo_id: null, intimacao_id: id, descricao: "Prazo", data_inicio: "2026-10-01",
  dias: 5, dias_uteis: true, data_fatal, cumprido: false, revisao_status
});

const rows = [
  row(1, "Pauta", {}, "sem_prazo_identificado"),
  row(2, "Sentença tardia", { prazo: prazo(2, "2026-10-30") }),
  row(3, "Decisão urgente", { prazo: prazo(3, "2026-10-09", "triagem") }),
  row(4, "Em análise", {}, "analisando")
];

it("abre em 'precisam de você', ordenado por vencimento e sem as intimações sem prazo", () => {
  render(<IntimacoesView rows={rows} offline={false} onOpen={vi.fn()} onPrepareWork={vi.fn()} />);
  const titles = screen.getAllByRole("article").map(item => item.querySelector("strong")?.textContent);
  expect(titles).toEqual(["Decisão urgente", "Sentença tardia", "Em análise"]);
  expect(screen.getByRole("button", { name: "Precisam de você (3)" }).getAttribute("aria-pressed")).toBe("true");
  expect(screen.queryByRole("button", { name: /Analisar prazos/ })).toBeNull();
});

it("separa as intimações sem prazo e não oferece minuta para elas", () => {
  render(<IntimacoesView rows={rows} offline={false} onOpen={vi.fn()} onPrepareWork={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Sem prazo (1)" }));
  expect(screen.getAllByRole("article")).toHaveLength(1);
  expect(screen.getByText("Pauta")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Preparar minuta" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Todas (4)" }));
  expect(screen.getAllByRole("article")).toHaveLength(4);
});
