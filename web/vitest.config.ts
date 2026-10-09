import { defineConfig } from "vitest/config";

/**
 * Pruebas unitarias (funciones puras de `src/lib`). Solo los `*.test.ts` de `src`: los `*.spec.ts`
 * de `tests/` son de Playwright y necesitan la web y la API en marcha.
 */
export default defineConfig({
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
  },
});
