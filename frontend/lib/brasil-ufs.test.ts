import { describe, expect, it } from "vitest";
import { BRASIL_UFS, filterBrasilUfs } from "./brasil-ufs";

describe("filterBrasilUfs", () => {
  it("mantem todas as 27 UFs brasileiras disponiveis", () => {
    expect(BRASIL_UFS).toHaveLength(27);
    expect(BRASIL_UFS.map((uf) => uf.sigla)).toContain("SP");
    expect(BRASIL_UFS.map((uf) => uf.sigla)).toContain("DF");
  });

  it("filtra por sigla ou nome ignorando acentos e caixa", () => {
    expect(filterBrasilUfs("rj").map((uf) => uf.sigla)).toEqual(["RJ"]);
    expect(filterBrasilUfs("goias").map((uf) => uf.sigla)).toEqual(["GO"]);
    expect(filterBrasilUfs("sao").map((uf) => uf.sigla)).toEqual(["SP"]);
  });
});
