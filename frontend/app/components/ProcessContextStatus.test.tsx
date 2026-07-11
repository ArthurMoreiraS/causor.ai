// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import ProcessContextStatus, { deriveUiState } from "./ProcessContextStatus";
import { ToastProvider } from "./Toast";

vi.mock("@/lib/api", () => ({
  statusAutos: vi.fn().mockResolvedValue({
    processo_id: 7,
    instancias: [
      {
        processo_instancia_id: 1,
        sistema: "PJe",
        tribunal: "TJMG",
        grau: "1",
        captura: {
          id: 10,
          processo_instancia_id: 1,
          generation: 1,
          status: "incomplete",
          expected_count: 5,
          captured_count: 3,
          missing_count: 2,
          error_code: "items_unverified",
          started_at: null,
          completed_at: null
        }
      }
    ]
  }),
  capturarAutos: vi.fn(),
  criarOverrideContexto: vi.fn(),
  proximoPassoContexto: vi.fn().mockResolvedValue({
    processo_id: 7,
    ready: false,
    next_step: "court_login",
    rota: { sistema: "PJe", tribunal: "TJMG", grau: "1" }
  }),
  loginTribunal: vi.fn(),
  statusSessaoTribunal: vi.fn()
}));

test("shows missing documents and opens the access wizard from Gerar minuta", async () => {
  render(
    <ToastProvider>
      <ProcessContextStatus processoId={7} />
    </ToastProvider>
  );
  expect(await screen.findByText("Contexto incompleto")).toBeInTheDocument();
  expect(screen.getByText(/2 documentos pendentes/)).toBeInTheDocument();

  // Bloqueado: "Gerar minuta" abre o assistente de acesso em vez de redigir direto.
  fireEvent.click(screen.getByRole("button", { name: "Gerar minuta" }));
  expect(
    await screen.findByLabelText("Assistente de acesso ao tribunal")
  ).toBeInTheDocument();
});

test("state derivation covers capture lifecycle", () => {
  expect(deriveUiState(null)).toBe("not_captured");
  expect(
    deriveUiState({
      processo_id: 1,
      instancias: [
        {
          processo_instancia_id: 1,
          sistema: "PJe",
          tribunal: "TJMG",
          grau: "1",
          captura: {
            id: 1,
            processo_instancia_id: 1,
            generation: 1,
            status: "downloading",
            expected_count: 5,
            captured_count: 1,
            missing_count: 0,
            error_code: null,
            started_at: null,
            completed_at: null
          }
        }
      ]
    })
  ).toBe("capturing");
  expect(
    deriveUiState({
      processo_id: 1,
      instancias: [
        {
          processo_instancia_id: 1,
          sistema: "PJe",
          tribunal: "TJMG",
          grau: "1",
          captura: {
            id: 1,
            processo_instancia_id: 1,
            generation: 1,
            status: "complete",
            expected_count: 5,
            captured_count: 5,
            missing_count: 0,
            error_code: null,
            started_at: null,
            completed_at: "2026-07-10T12:00:00Z"
          }
        }
      ]
    })
  ).toBe("ready");
});
