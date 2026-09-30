import { expect, test } from "@playwright/test";

/** Mónaco 1956: Fangio abandonó con el #20 y terminó 2.º con el coche de Collins, el #26. */
const MONACO_1956 = 50;
/** Estados Unidos 2006: corrieron Michael y Ralf Schumacher. */
const UNITED_STATES_2006 = 760;

test("un piloto con dos coches tiene una serie por coche", async ({ page }) => {
  await page.goto(`/es/races/${MONACO_1956}/lap-chart`);
  await page.getByText("Ver los datos como tabla").click();
  const table = page.getByRole("table", { name: /Resumen por piloto/ });
  await expect(table.getByRole("rowheader", { name: "Juan Manuel Fangio (#20)" })).toBeVisible();
  await expect(table.getByRole("rowheader", { name: "Juan Manuel Fangio (#26)" })).toBeVisible();
});

test("los dos Schumacher tienen códigos distintos", async ({ page }) => {
  await page.goto(`/es/races/${UNITED_STATES_2006}/pace`);
  await expect(page.locator("abbr[title='Michael Schumacher']").first()).toHaveText("MSC");
  await expect(page.locator("abbr[title='Ralf Schumacher']").first()).toHaveText("RSC");
});
