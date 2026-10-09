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

it("hides process deletion from who may not delete it", () => {
  renderDrawer();

  expect(screen.queryByRole("button", { name: "Excluir processo" })).toBeNull();
});
