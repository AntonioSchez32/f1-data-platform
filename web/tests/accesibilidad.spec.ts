import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// Bahrein 2024: carrera con todas las secciones (vueltas, neumáticos, telemetría).
const RACE = 1102;

const PAGES = [
  "/es",
  "/en",
  "/es/seasons",
  "/es/seasons/2021",
  "/es/seasons/1950",
  `/es/races/${RACE}`,
  `/es/races/${RACE}/qualifying`,
  `/es/races/${RACE}/lap-chart`,
  `/es/races/${RACE}/tyres`,
  `/es/races/${RACE}/pace`,
  `/es/races/${RACE}/pitstops`,
  `/es/races/${RACE}/telemetry`,
  "/es/drivers",
  "/es/drivers?q=hamil",
  "/es/drivers/michael-schumacher",
  "/es/constructors",
  "/es/constructors/ferrari",
  "/es/records",
  "/es/records?entity=constructors&from=2000&to=2010",
  "/es/quality",
  "/en/races/1102/pace",
  // Coche compartido (Fangio con el #20 y el #26) y códigos MSC/RSC.
  "/es/races/50/lap-chart",
  "/es/races/760/pace",
  // Correcciones de agregados (C4): temporada sin clasificar, acumulados frente al compañero y
  // puntos de constructor nulos antes de 1958.
  "/es/drivers/ayrton-senna",
  "/en/drivers/juan-manuel-fangio",
  "/es/constructors/gordini",
  "/es/records?entity=constructors&from=1950&to=1960&order=points",
];

for (const path of PAGES) {
  test(`sin errores de accesibilidad WCAG 2.2 AA: ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();
    const summary = results.violations.map((v) => `${v.id}: ${v.nodes.length} nodos · ${v.help}`);
    expect(summary, summary.join("\n")).toEqual([]);
  });
}

test("cada gráfico tiene resumen en texto y tabla alternativa", async ({ page }) => {
  for (const path of [`/es/races/${RACE}/pace`, "/es/seasons/2021", "/es/drivers/michael-schumacher", "/es/drivers/ayrton-senna"]) {
    await page.goto(path);
    const figures = page.locator("figure");
    const count = await figures.count();
    expect(count).toBeGreaterThan(0);
    for (let i = 0; i < count; i++) {
      const figure = figures.nth(i);
      await expect(figure.locator("figcaption")).not.toBeEmpty();
      await expect(figure.locator("details summary")).toHaveCount(1);
    }
  }
});

test.describe("tema oscuro", () => {
  test.use({ colorScheme: "dark" });
  for (const path of ["/es", `/es/races/${RACE}/tyres`, "/es/quality", "/es/drivers/michael-schumacher"]) {
    test(`contraste en tema oscuro: ${path}`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const results = await new AxeBuilder({ page }).withTags(["wcag2aa"]).analyze();
      const summary = results.violations.map((v) => `${v.id}: ${v.nodes.length} nodos · ${v.help}`);
      expect(summary, summary.join("\n")).toEqual([]);
    });
  }
});
