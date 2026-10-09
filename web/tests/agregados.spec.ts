import { expect, test } from "@playwright/test";

/** Correcciones de agregados (C4, decisiones 36, 37 y 45) y formato del tiempo (WEB-01). */

test("el tiempo de carrera con 0 minutos se formatea bien (Singapur 2014)", async ({ page }) => {
  await page.goto("/es/races/911");
  await expect(page.getByText("2:00:04.795").first()).toBeVisible();
});

test("una temporada sin clasificación final aparece como «sin clasificar»", async ({ page }) => {
  await page.goto("/es/drivers/ayrton-senna");
  await page.locator("#temporadas").getByText("Ver los datos como tabla").click();
  const row = page.getByRole("row", { name: /^1994/ });
  await expect(row.getByText("sin clasificar")).toBeVisible();
  await expect(row.getByText("3 / 3")).toBeVisible();
});

test("los puntos frente al compañero cuentan los del piloto una vez (Fangio 1955)", async ({ page }) => {
  await page.goto("/es/drivers/juan-manuel-fangio");
  const figure = page.locator("figure").filter({ hasText: "Puntos frente al mejor compañero de cada carrera" });
  await figure.getByText("Ver los datos como tabla").click();
  const row = figure.getByRole("row", { name: /^1955/ });
  await expect(row.getByRole("cell").nth(0)).toHaveText("41");
  await expect(row.getByRole("cell").nth(1)).toHaveText("28");
});

test("sin campeonato de constructores antes de 1958, los «Puntos» quedan en blanco", async ({ page }) => {
  await page.goto("/es/constructors/gordini");
  await expect(page.getByText("no había campeonato de constructores antes de 1958").first()).toBeAttached();
  await expect(page.getByText("Puntos históricos").first()).toBeVisible();
});
