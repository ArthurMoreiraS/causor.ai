import { describe, expect, it } from "vitest";
import { formatCnj, sistemaBadge, sistemaNome } from "./format";
import { decodeEntities, previewText } from "./sanitize";

describe("formatCnj", () => {
  it("formats twenty digits in the CNJ layout", () => {
    expect(formatCnj("10044176320264013400")).toBe("1004417-63.2026.4.01.3400");
  });

  it("keeps values that are already formatted or are not CNJ numbers", () => {
    expect(formatCnj("1004417-63.2026.4.01.3400")).toBe("1004417-63.2026.4.01.3400");
    expect(formatCnj("AREsp 3174902")).toBe("AREsp 3174902");
    expect(formatCnj(null)).toBe("");
  });
});

describe("sistemaNome", () => {
  it("writes court systems the way courts do", () => {
    expect(sistemaNome("PJE")).toBe("PJe");
    expect(sistemaNome("EPROC")).toBe("eproc");
    expect(sistemaNome("E-STJ")).toBe("e-STJ");
    expect(sistemaNome("SistemaX")).toBe("SistemaX");
    expect(sistemaBadge("PJE").label).toBe("PJe");
  });
});

describe("decodeEntities", () => {
  it("decodes named, accented and numeric entities", () => {
    expect(decodeEntities("Agravo N&ordm; 50 Ju&iacute;za Federal")).toBe("Agravo Nº 50 Juíza Federal");
    expect(decodeEntities("A&ccedil;&atilde;o &#233; &#x2013; ok")).toBe("Ação é – ok");
  });

  it("keeps unknown entities and returns plain text", () => {
    expect(decodeEntities("&foo; &lt;b&gt;")).toBe("&foo; <b>");
  });

  it("applies to list previews", () => {
    expect(previewText("<p>Relatora: Ju&iacute;za</p>")).toBe("Relatora: Juíza");
  });
});
