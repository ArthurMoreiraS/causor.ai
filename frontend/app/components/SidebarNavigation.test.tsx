// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import SidebarNavigation from "./SidebarNavigation";

afterEach(cleanup);

it("distingue os ícones de Trabalhos e Minutas na navegação", () => {
  render(<SidebarNavigation view="dashboard" onNavigate={vi.fn()} />);
  const workIcon = screen.getByRole("button", { name: "Trabalhos" }).querySelector("svg");
  const draftIcon = screen.getByRole("button", { name: "Minutas" }).querySelector("svg");
  expect(workIcon?.classList.contains("lucide-briefcase-business")).toBe(true);
  expect(draftIcon?.classList.contains("lucide-file-pen-line")).toBe(true);
});
