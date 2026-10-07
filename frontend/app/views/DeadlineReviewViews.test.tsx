// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Prazo } from "@/lib/api";
import type { PrazoRow } from "@/lib/views";
import HomeDashboard from "./HomeDashboard";
import PrazosView from "./PrazosView";

afterEach(cleanup);

const provisional: Prazo = {
  id: 1, processo_id: null, intimacao_id: 4, descricao: "Manifestação",
  data_inicio: "2026-09-28", dias: 5, dias_uteis: true,
  data_fatal: "2026-10-05", cumprido: false, revisao_status: "calculado_a_revisar"
};
const row: PrazoRow = { prazo: provisional, processo: null, intimacao: null, peticao: null, dias: -1 };

it("shows provisional date as review work, without claiming a confirmed due date", () => {
  const navigate = vi.fn();
  render(<HomeDashboard
    metrics={{ monitored: 1, captured: 1, pending: 1, reviewPending: 1, confirmedPending: 0,
      highRisk: 0, overdue: 0, drafts: 0, approved: 0, withoutDraft: 1, compliance: 100 }}
    unlinkedNotices={0} prazoRows={[row]} operationalConnectors={[]} offline={false} busy={null}
    onOpenOab={vi.fn()} onOpenAssistant={vi.fn()} onNavigate={navigate} greetingName={null}
  />);
  expect(screen.getByText(/aguardando revisão/)).toBeTruthy();
  expect(screen.queryByText(/Manifestação vence em/)).toBeNull();
  expect(screen.getByText("05/10 · conferir")).toBeTruthy();
  expect(screen.getByText("a revisar")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Revisar prazos" }));
  expect(navigate).toHaveBeenCalledWith("prazos");
});

it("blocks fulfillment until confirmation and opens captured notice for review", () => {
  const done = vi.fn();
  const open = vi.fn();
  render(<PrazosView rows={[{ ...row, intimacao: {
    id: 4, processo_id: null, fonte: "DJEN", numero_processo: null, tribunal: "TJSP",
    tipo_comunicacao: "Intimação", teor: "", data_disponibilizacao: "2026-09-25", data_publicacao: null
  } }]} busy={null} offline={false} onOpen={open} onDonePrazo={done} onEditPrazo={vi.fn()} />);
  const fulfill = screen.getByRole("button", { name: "Cumprir" }) as HTMLButtonElement;
  expect(fulfill.disabled).toBe(true);
  expect(screen.getByText("a revisar")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Conferir" }));
  expect(open).toHaveBeenCalledWith({ kind: "intimacao", id: 4 });
  expect(done).not.toHaveBeenCalled();
});
