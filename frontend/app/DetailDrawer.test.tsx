// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Processo } from "@/lib/api";
import DetailDrawer from "./DetailDrawer";

vi.mock("./components/ConfirmarPrazo", () => ({ default: () => null }));

const processo: Processo = { id: 4, numero: "50671771320264025101", classe: null, tribunal: "TRF2", orgao_julgador: null, sistema: null };

afterEach(cleanup);

function renderDrawer(onDeleteProcess?: (p: Processo) => void) {
  render(<DetailDrawer selection={{ kind: "processo", id: 4 }} processos={[processo]} intimacoes={[]} prazos={[]}
    peticoes={[]} busy={null} offline={false} onClose={vi.fn()} onSelect={vi.fn()} onPrepareWork={vi.fn()}
    onOpenPeticao={vi.fn()} onDeleteProcess={onDeleteProcess} />);
}

it("offers process deletion to who may delete it", () => {
  const onDelete = vi.fn();
  renderDrawer(onDelete);

  fireEvent.click(screen.getByRole("button", { name: "Excluir processo" }));

  expect(onDelete).toHaveBeenCalledWith(processo);
});

function renderNotice(avisos?: string[]) {
  const intimacao = { id: 9, processo_id: 4, fonte: "DJEN", numero_processo: processo.numero, tribunal: "TRF2",
    tipo_comunicacao: "Intimação", teor: "Intime-se.", data_disponibilizacao: "2026-10-01", data_publicacao: null,
    prazo_analise: { status: "calculado_a_revisar", avisos } };
  render(<DetailDrawer selection={{ kind: "intimacao", id: 9 }} processos={[processo]} intimacoes={[intimacao]}
    prazos={[]} peticoes={[]} busy={null} offline={false} onClose={vi.fn()} onSelect={vi.fn()}
    onPrepareWork={vi.fn()} onOpenPeticao={vi.fn()} />);
}

it("shows reading warnings on the notice without touching the deadline", () => {
  renderNotice(["O texto parece trazer mais de um ato ou parte; confira a qual o prazo se refere."]);

  expect(screen.getByRole("note").textContent).toBe(
    "Atenção: O texto parece trazer mais de um ato ou parte; confira a qual o prazo se refere.");
});

it("shows no warning when the analysis has none", () => {
  renderNotice();

  expect(screen.queryByRole("note")).toBeNull();
});

it("hides process deletion from who may not delete it", () => {
  renderDrawer();

  expect(screen.queryByRole("button", { name: "Excluir processo" })).toBeNull();
});
