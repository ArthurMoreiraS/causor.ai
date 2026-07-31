// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import AcessoTribunaisPanel from "./AcessoTribunaisPanel";
import { AcessoTribunal, listarAcessoTribunais } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  listarAcessoTribunais: vi.fn()
}));

const pronto: AcessoTribunal = {
  sistema: "EPROC",
  tribunal: "TJTO",
  grau: "1",
  processos: 12,
  ler_autos: { disponivel: true, via: "computador", falta: null },
  protocolar: { disponivel: true, via: "computador", falta: null },
  mni_disponivel: false
};

const sessaoExpirada: AcessoTribunal = {
  ...pronto,
  tribunal: "TJMT",
  processos: 8,
  ler_autos: { disponivel: false, via: null, falta: "reconectar" },
  protocolar: { disponivel: false, via: null, falta: "reconectar" }
};

const naoPareado: AcessoTribunal = {
  ...pronto,
  tribunal: "TJSP",
  sistema: "ESAJ",
  processos: 5,
  ler_autos: { disponivel: false, via: null, falta: "parear" },
  protocolar: { disponivel: false, via: null, falta: "parear" }
};

const leituraOficial: AcessoTribunal = {
  ...pronto,
  tribunal: "TJPI",
  sistema: "PJe",
  processos: 2,
  ler_autos: { disponivel: true, via: "oficial", falta: null },
  protocolar: { disponivel: false, via: null, falta: "parear" },
  mni_disponivel: true
};

beforeEach(() => {
  vi.mocked(listarAcessoTribunais).mockResolvedValue([pronto]);
});

afterEach(cleanup);

test("mostra cada rota com as duas capacidades nomeadas", async () => {
  render(<AcessoTribunaisPanel offline={false} />);

  expect(await screen.findByText(/TJTO/)).toBeInTheDocument();
  expect(screen.getByText("Ler os autos")).toBeInTheDocument();
  expect(screen.getByText("Protocolar")).toBeInTheDocument();
  expect(screen.getAllByText(/pelo seu computador/).length).toBe(2);
});

test("resume quantas rotas estão prontas", async () => {
  vi.mocked(listarAcessoTribunais).mockResolvedValue([pronto, sessaoExpirada]);
  render(<AcessoTribunaisPanel offline={false} />);

  expect(await screen.findByText("1 de 2 prontos")).toBeInTheDocument();
});

test("sessão expirada pede para reconectar", async () => {
  vi.mocked(listarAcessoTribunais).mockResolvedValue([sessaoExpirada]);
  render(<AcessoTribunaisPanel offline={false} />);

  expect((await screen.findAllByText(/a sessão expirou/)).length).toBe(2);
});

test("sem computador pareado a rota diz o que falta", async () => {
  vi.mocked(listarAcessoTribunais).mockResolvedValue([naoPareado]);
  render(<AcessoTribunaisPanel offline={false} />);

  expect((await screen.findAllByText(/pareie o seu computador/i)).length).toBe(2);
});

test("leitura pelo canal oficial ainda exige o computador para protocolar", async () => {
  vi.mocked(listarAcessoTribunais).mockResolvedValue([leituraOficial]);
  render(<AcessoTribunaisPanel offline={false} />);

  expect(await screen.findByText(/direto do tribunal/i)).toBeInTheDocument();
  expect(screen.getByText(/pareie o seu computador/i)).toBeInTheDocument();
});

test("nenhum texto visível usa jargão técnico", async () => {
  vi.mocked(listarAcessoTribunais).mockResolvedValue([
    pronto,
    sessaoExpirada,
    naoPareado,
    leituraOficial
  ]);
  const { container } = render(<AcessoTribunaisPanel offline={false} />);
  await screen.findByText(/TJTO/);

  const texto = container.textContent ?? "";
  expect(texto).not.toMatch(/MNI/);
  expect(texto).not.toMatch(/agente/i);
});

test("estado vazio explica que o painel se preenche com os processos", async () => {
  vi.mocked(listarAcessoTribunais).mockResolvedValue([]);
  render(<AcessoTribunaisPanel offline={false} />);

  expect(await screen.findByText(/Nenhum tribunal/)).toBeInTheDocument();
});
