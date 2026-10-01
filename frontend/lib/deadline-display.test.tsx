// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { daysUntil } from "./format";
import { DeadlineBadge } from "../app/components/ui";

afterEach(() => { cleanup(); vi.useRealTimers(); });

it("uses São Paulo civil dates even before UTC midnight", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-09-30T02:00:00Z"));
  expect(daysUntil("2026-09-29")).toBe(0);
  expect(daysUntil("2026-09-30")).toBe(1);
  render(<DeadlineBadge prazo={{ data_fatal: "2026-09-29", cumprido: false, revisao_status: "confirmado" }} />);
  expect(screen.getByText("Hoje")).toBeTruthy();
});

it("distinguishes automatic suggestions and unresolved analysis", () => {
  render(<>
    <DeadlineBadge prazo={{ data_fatal: "2026-09-29", cumprido: false, revisao_status: "calculado_a_revisar" }} />
    <DeadlineBadge prazo={null} analise={{ status: "falha", motivo: "Provedor indisponível" }} />
  </>);
  expect(screen.getByText("Calculado · revisar")).toBeTruthy();
  expect(screen.getByText("Falha na análise").getAttribute("title")).toBe("Provedor indisponível");
});
