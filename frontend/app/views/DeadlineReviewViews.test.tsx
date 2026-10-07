// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Prazo } from "@/lib/api";
import type { PrazoRow } from "@/lib/views";
import HomeDashboard from "./HomeDashboard";
import PrazosView from "./PrazosView";

afterEach(cleanup);

const provisional: Prazo = {
  id: 1, processo_id: null, intimacao_id: 4, descricao: "Triagem — prazo real não identificado",
  data_inicio: "2026-09-28", dias: 5, dias_uteis: true,
  data_fatal: "2026-10-05", cumprido: false, revisao_status: "triagem"
};
const row: PrazoRow = { prazo: provisional, processo: null, intimacao: null, peticao: null, dias: -1 };
const automatic: PrazoRow = { ...row, prazo: { ...provisional, id: 2, descricao: "Apelação",
  revisao_status: "calculado_a_revisar" } };

it("shows a triage date as review work, without claiming a due date", () => {
  const navigate = vi.fn();
  render(<HomeDashboard
    metrics={{ monitored: 1, captured: 1, pending: 1, reviewPending: 1, confirmedPending: 0,
      highRisk: 0, overdue: 0, drafts: 0, approved: 0, withoutDraft: 1, compliance: 100 }}
    unlinkedNotices={0} prazoRows={[row]} operationalConnectors={[]} offline={false} busy={null}
    onOpenOab={vi.fn()} onOpenAssistant={vi.fn()} onNavigate={navigate} greetingName={null}
  />);
  expect(screen.getByText(/aguardando revisão/)).toBeTruthy();
  expect(screen.queryByText(/vence em/)).toBeNull();
  expect(screen.getByText("Triagem · 05/10")).toBeTruthy();
  expect(screen.getByText("triagem")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Revisar prazos" }));
  expect(navigate).toHaveBeenCalledWith("prazos");
});

it("treats an automatic deadline as the next due date", () => {
  render(<HomeDashboard
    metrics={{ monitored: 1, captured: 1, pending: 1, reviewPending: 0, confirmedPending: 1,
      highRisk: 0, overdue: 0, drafts: 0, approved: 0, withoutDraft: 1, compliance: 100 }}
    unlinkedNotices={0} prazoRows={[{ ...automatic, dias: 3 }]} operationalConnectors={[]} offline={false}
    busy={null} onOpenOab={vi.fn()} onOpenAssistant={vi.fn()} onNavigate={vi.fn()} greetingName={null}
  />);
  expect(screen.getByText(/Apelação vence em 05\/10\/2026/)).toBeTruthy();
});

it("allows fulfilling without confirmation and opens a triage notice for review", () => {
  const done = vi.fn();
  const open = vi.fn();
  render(<PrazosView rows={[{ ...row, intimacao: {
    id: 4, processo_id: null, fonte: "DJEN", numero_processo: null, tribunal: "TJSP",
    tipo_comunicacao: "Intimação", teor: "", data_disponibilizacao: "2026-09-25", data_publicacao: null
  } }]} busy={null} offline={false} onOpen={open} onDonePrazo={done} onEditPrazo={vi.fn()} />);
  const fulfill = screen.getByRole("button", { name: "Cumprir" }) as HTMLButtonElement;
  expect(fulfill.disabled).toBe(false);
  expect(screen.getByText("triagem")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Conferir" }));
  expect(open).toHaveBeenCalledWith({ kind: "intimacao", id: 4 });
  fireEvent.click(fulfill);
  expect(done).toHaveBeenCalledWith(provisional);
});
