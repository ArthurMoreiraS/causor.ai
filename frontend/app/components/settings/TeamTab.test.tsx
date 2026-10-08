// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { alterarMembro, carregarUsuarioAtual, convidarMembro, listarUsuarios, type CurrentUser, type Usuario } from "@/lib/api";
import { ToastProvider } from "../Toast";
import TeamTab from "./TeamTab";

vi.mock("@/lib/api", () => ({
  alterarMembro: vi.fn(), carregarUsuarioAtual: vi.fn(), convidarMembro: vi.fn(),
  listarUsuarios: vi.fn(), reenviarConvite: vi.fn()
}));
afterEach(cleanup);

const socia = { id: 1, escritorio_id: 1, nome: "Sócia", email: "socia@example.com", oab: null, oab_uf: null,
  papel: "administrador", ativo: true, convite_pendente: false } as Usuario;
const bia = { ...socia, id: 2, nome: "Bia", email: "bia@example.com", papel: "assistente", convite_pendente: true } as Usuario;

function me(papel: CurrentUser["papel"], permissoes: CurrentUser["permissoes"]): CurrentUser {
  return { usuario_id: 1, escritorio_id: 1, email: "socia@example.com", papel, permissoes };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listarUsuarios).mockResolvedValue([socia, bia]);
});

function renderTab() {
  render(<ToastProvider><TeamTab offline={false} /></ToastProvider>);
}

it("administrador convida membro com papel", async () => {
  vi.mocked(carregarUsuarioAtual).mockResolvedValue(me("administrador", ["gerir_equipe", "configurar_escritorio", "aprovar_minuta", "decidir_prazo"]));
  const novo = { ...bia, id: 3, nome: "Caio", email: "caio@example.com", papel: "advogado" } as Usuario;
  vi.mocked(convidarMembro).mockResolvedValue({ membro: novo, convite: "enviado" });
  renderTab();

  fireEvent.change(await screen.findByLabelText("Nome"), { target: { value: "Caio" } });
  fireEvent.change(screen.getByLabelText("E-mail"), { target: { value: "caio@example.com" } });
  fireEvent.click(screen.getByRole("button", { name: "Enviar convite" }));

  await waitFor(() => expect(convidarMembro).toHaveBeenCalledWith({ nome: "Caio", email: "caio@example.com", papel: "advogado" }));
  expect(await screen.findByText("Caio")).toBeTruthy();
  expect(await screen.findByText("Convite enviado")).toBeTruthy();
});

it("administrador desativa outro membro, mas não a si mesmo", async () => {
  vi.mocked(carregarUsuarioAtual).mockResolvedValue(me("administrador", ["gerir_equipe"]));
  vi.mocked(alterarMembro).mockResolvedValue({ ...bia, ativo: false });
  renderTab();

  const desativar = await screen.findAllByRole("button", { name: "Desativar" });
  expect(desativar).toHaveLength(1);
  fireEvent.click(desativar[0]);

  await waitFor(() => expect(alterarMembro).toHaveBeenCalledWith(2, { ativo: false }));
  expect(await screen.findByText("Desativado")).toBeTruthy();
});

it("assistente vê a equipe sem poder alterá-la", async () => {
  vi.mocked(carregarUsuarioAtual).mockResolvedValue(me("assistente", []));
  renderTab();

  expect(await screen.findByText("Só administradores convidam, mudam papéis e desativam membros.")).toBeTruthy();
  expect(screen.getByText("Bia")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Enviar convite" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Desativar" })).toBeNull();
});
