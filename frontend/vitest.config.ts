import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// O tsconfig usa "jsx": "preserve" (Next transforma). O Vitest (Vite 8 /
// rolldown) precisa transformar JSX por conta própria — via `oxc` — e
// resolver o alias "@/" do tsconfig.
export default defineConfig({
  oxc: {
    jsx: { runtime: "automatic" }
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL(".", import.meta.url)).replace(/[\\/]+$/, "")
    }
  }
});
