import { defineConfig, devices } from "@playwright/test";

/**
 * Pruebas de extremo a extremo y de accesibilidad (axe) contra la web compilada.
 * Necesitan la API en marcha (F1_API_URL, por defecto http://127.0.0.1:8000).
 * En local se usa el Edge del sistema; en la CI, el Chromium de Playwright.
 * Con BASE_URL se prueban contra una web ya desplegada (p. ej. la de Vercel).
 */
const PORT = 3100;
const BASE_URL = process.env.BASE_URL;

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: BASE_URL ?? `http://127.0.0.1:${PORT}`,
    channel: process.env.CI ? undefined : "msedge",
  },
  projects: [
    { name: "escritorio", use: { ...devices["Desktop Chrome"], channel: process.env.CI ? undefined : "msedge" } },
    {
      name: "movil",
      use: { ...devices["Pixel 7"], channel: process.env.CI ? undefined : "msedge" },
      testMatch: /navegacion/,
    },
  ],
  webServer: BASE_URL
    ? undefined
    : {
        command: `npx next start --port ${PORT}`,
        url: `http://127.0.0.1:${PORT}/es`,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
