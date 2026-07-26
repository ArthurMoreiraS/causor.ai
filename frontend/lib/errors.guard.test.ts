import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "vitest";

// O helper `humanError` ja existia e mesmo assim o padrao cru voltou: em
// 22/07 ele estava aplicado em 2 componentes e ausente em outros 22, entao
// "Failed to fetch" continuava chegando em ingles para o advogado. Teste
// unitario de componente nao pega isso — so quem varre a arvore pega. Este
// teste falha no CI quando o padrao reaparece, em vez de na tela do piloto.

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const DIRS = ["app", "lib"];

// `lib/errors.ts` e a unica implementacao legitima do desempacotamento.
const EXEMPT = new Set(["lib/errors.ts"]);

// Casa `err instanceof Error ? err.message`, com qualquer nome de variavel,
// exigindo que os dois lados sejam a MESMA variavel (backreference).
const RAW_UNWRAP = /(\w+) instanceof Error \? \1\.message/;

function sourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(join(ROOT, dir), { withFileTypes: true })) {
    const rel = `${dir}/${entry.name}`;
    if (entry.isDirectory()) {
      out.push(...sourceFiles(rel));
    } else if (/\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) {
      out.push(rel);
    }
  }
  return out;
}

// Guarda da guarda: um detector que nao detecta nada passaria vazio para
// sempre e daria falsa seguranca.
test("o detector reconhece o padrao cru", () => {
  expect(RAW_UNWRAP.test('setError(err instanceof Error ? err.message : "x")')).toBe(true);
  expect(RAW_UNWRAP.test('setError(erro instanceof Error ? erro.message : "x")')).toBe(true);
  expect(RAW_UNWRAP.test('setError(humanError(err, "x"))')).toBe(false);
  // Variaveis diferentes dos dois lados nao sao o padrao que nos interessa.
  expect(RAW_UNWRAP.test("err instanceof Error ? outro.message")).toBe(false);
});

test("nenhum componente desempacota Error cru na tela — use humanError", () => {
  const scanned = DIRS.flatMap((dir) => sourceFiles(dir));
  expect(scanned.length).toBeGreaterThan(20); // a varredura achou arquivos

  const offenders = scanned
    .filter((rel) => !EXEMPT.has(rel))
    .filter((rel) => RAW_UNWRAP.test(readFileSync(join(ROOT, rel), "utf8")));

  expect(offenders, "use humanError(err, \"...\") nestes arquivos").toEqual([]);
});
