// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { confirmarPrazoIntimacao } from "@/lib/api";
import ConfirmarPrazo from "./ConfirmarPrazo";

vi.mock("@/lib/api", () => ({ confirmarPrazoIntimacao: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("só calcula com dados e fundamento confirmados e avisa o painel após sucesso", async () => {
  const prazo = { id: 9, data_fatal: "2026-10-10" };
  vi.mocked(confirmarPrazoIntimacao).mockResolvedValue(prazo as Awaited<ReturnType<typeof confirmarPrazoIntimacao>>);
  const onConfirmed = vi.fn();
  render(<ConfirmarPrazo intimacaoId={8} onConfirmed={onConfirmed} />);
  fireEvent.click(screen.getByText("Revisar e calcular prazo"));
  const submit = screen.getByRole("button", { name: "Confirmar e calcular prazo" });
  expect((submit as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText(/Data base confirmada/), { target: { value: "2026-09-25" } });
  fireEvent.change(screen.getByLabelText(/Duração em dias/), { target: { value: "5" } });
  fireEvent.change(screen.getByLabelText(/Fundamento da duração/), { target: { value: "Prazo legal conferido pelo advogado" } });
  fireEvent.click(submit);
  await waitFor(() => expect(onConfirmed).toHaveBeenCalledWith(prazo));
  expect(confirmarPrazoIntimacao).toHaveBeenCalledWith(8, expect.objectContaining({ data_base: "2026-09-25", dias: 5 }));
  expect(screen.getByRole("status").textContent).toContain("10/10/2026");
});

it("preenche sugestão recebida depois do polling enquanto o formulário está intacto", () => {
  const { rerender } = render(<ConfirmarPrazo intimacaoId={8} />);
  const base = screen.getByLabelText("Data base confirmada (excluída da contagem)") as HTMLInputElement;
  const days = screen.getByLabelText("Duração em dias") as HTMLInputElement;
  expect(base.value).toBe("");
  expect(days.value).toBe("");
  rerender(<ConfirmarPrazo intimacaoId={8} analise={{ publicacao: "2026-09-28", dias: 5 }} />);
  expect(base.value).toBe("2026-09-28");
  expect(days.value).toBe("5");
});

it("não sobrescreve os campos editados quando uma nova sugestão chega", () => {
  const { rerender } = render(<ConfirmarPrazo intimacaoId={8} analise={{ publicacao: "2026-09-28", dias: 5 }} />);
  const base = screen.getByLabelText("Data base confirmada (excluída da contagem)") as HTMLInputElement;
  const days = screen.getByLabelText("Duração em dias") as HTMLInputElement;
  fireEvent.change(base, { target: { value: "2026-09-29" } });
  rerender(<ConfirmarPrazo intimacaoId={8} analise={{ publicacao: "2026-10-01", dias: 15 }} />);
  expect(base.value).toBe("2026-09-29");
  expect(days.value).toBe("5");
});
