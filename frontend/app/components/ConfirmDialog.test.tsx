// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ConfirmProvider, useConfirm, type ConfirmOptions } from "./ConfirmDialog";

afterEach(cleanup);

function Asker({ options, onAnswer }: { options: ConfirmOptions; onAnswer: (confirmed: boolean) => void }) {
  const confirm = useConfirm();
  return <button type="button" onClick={() => void confirm(options).then(onAnswer)}>Perguntar</button>;
}

function ask(options: ConfirmOptions = { title: "Excluir?", confirmLabel: "Excluir" }) {
  const onAnswer = vi.fn();
  render(<ConfirmProvider><Asker options={options} onAnswer={onAnswer} /></ConfirmProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Perguntar" }));
  return { onAnswer, dialog: screen.getByRole("dialog", { name: options.title }) };
}

it("resolve verdadeiro ao confirmar e fecha o diálogo", async () => {
  const { onAnswer, dialog } = ask({ title: "Excluir?", description: "Não pode ser desfeito.", confirmLabel: "Excluir" });
  expect(within(dialog).getByText("Não pode ser desfeito.")).toBeTruthy();
  fireEvent.click(within(dialog).getByRole("button", { name: "Excluir" }));
  await waitFor(() => expect(onAnswer).toHaveBeenCalledWith(true));
  expect(screen.queryByRole("dialog")).toBeNull();
});

it("começa com o foco em Cancelar e resolve falso ao cancelar", async () => {
  const { onAnswer, dialog } = ask();
  const cancel = within(dialog).getByRole("button", { name: "Cancelar" });
  expect(document.activeElement).toBe(cancel);
  fireEvent.click(cancel);
  await waitFor(() => expect(onAnswer).toHaveBeenCalledWith(false));
});

it("resolve falso com Esc", async () => {
  const { onAnswer } = ask();
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(onAnswer).toHaveBeenCalledWith(false));
  expect(screen.queryByRole("dialog")).toBeNull();
});
