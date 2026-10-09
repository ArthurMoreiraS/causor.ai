import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

// Guarda do sistema visual "Papel e tinta": tamanhos, pesos, famílias e cores
// só podem vir dos tokens de app/styles/tokens.css. Antes desta guarda o CSS
// tinha 30 tamanhos de fonte, pesos que a fonte não carregava e rótulos em
// mono caixa alta; cada tela nova copiava um padrão diferente.

const APP = join(__dirname, "..", "app");
const TOKENS = join(APP, "styles", "tokens.css");

function cssFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) return cssFiles(full);
    return name.endsWith(".css") ? [full] : [];
  });
}

type Declaration = { file: string; prop: string; value: string };

function declarations(file: string): Declaration[] {
  const source = readFileSync(file, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/@font-face\s*\{[^}]*\}/g, "");
  const found: Declaration[] = [];
  for (const block of source.matchAll(/\{([^{}]*)\}/g)) {
    for (const decl of block[1].matchAll(/([a-z-]+)\s*:\s*([^;]+)/g)) {
      if (decl[1].startsWith("--")) continue;
      found.push({ file: relative(APP, file), prop: decl[1], value: decl[2].trim() });
    }
  }
  return found;
}

const all = cssFiles(APP).flatMap(declarations);
const outsideTokens = cssFiles(APP).filter((file) => file !== TOKENS).flatMap(declarations);
const show = (items: Declaration[]) => items.map((d) => `${d.file}: ${d.prop}: ${d.value}`);

describe("design tokens", () => {
  it("uses only the type scale for font sizes", () => {
    const bad = all.filter((d) => d.prop === "font-size" && !/^(var\(--text-(xs|sm|base|md|lg|xl|display)\)|inherit)$/.test(d.value));
    expect(show(bad)).toEqual([]);
  });

  it("uses only the loaded weights", () => {
    const bad = all.filter((d) => d.prop === "font-weight" && !/^(400|500|600|inherit|normal)$/.test(d.value));
    expect(show(bad)).toEqual([]);
  });

  it("uses only the font family tokens", () => {
    const bad = all.filter((d) => d.prop === "font-family" && !/^(var\(--font-(ui|display|mono)\)|inherit)$/.test(d.value));
    expect(show(bad)).toEqual([]);
  });

  it("keeps labels in sentence case without extra tracking", () => {
    const upper = all.filter((d) => d.prop === "text-transform" && d.value === "uppercase");
    const tracking = all.filter((d) => d.prop === "letter-spacing" && !/^(0|normal|var\(--tracking-display\))$/.test(d.value));
    expect(show([...upper, ...tracking])).toEqual([]);
  });

  it("keeps literal colors inside the token file", () => {
    const bad = outsideTokens.filter((d) => /#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i.test(d.value));
    expect(show(bad)).toEqual([]);
  });
});
