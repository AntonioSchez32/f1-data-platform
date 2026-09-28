import { expect, test } from "@playwright/test";

test("la raíz redirige al idioma del navegador", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/(es|en)$/);
});

test("el enlace para saltar al contenido es el primer elemento enfocable", async ({ page }) => {
  await page.goto("/es");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Saltar al contenido" });
  await expect(skip).toBeFocused();
  await skip.press("Enter");
  await expect(page.locator("#contenido")).toBeFocused();
});

test("del inicio a una carrera y sus pestañas", async ({ page }) => {
  await page.goto("/es");
  await page.getByRole("link", { name: "Resultado completo" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const tabs = page.getByRole("navigation", { name: "Secciones de la carrera" });
  await tabs.getByRole("link", { name: "Vuelta a vuelta" }).click();
  await expect(tabs.getByRole("link", { name: "Vuelta a vuelta" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("img", { name: /Posiciones vuelta a vuelta/ })).toBeVisible();
});

test("el buscador de pilotos funciona sin JavaScript", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto("/es/drivers");
  await page.getByRole("searchbox", { name: "Nombre del piloto" }).fill("senna");
  await page.getByRole("button", { name: "Buscar" }).click();
  await expect(page.getByRole("link", { name: "Ayrton Senna" })).toBeVisible();
  await context.close();
});

test("el cambio de idioma conserva la página", async ({ page }) => {
  await page.goto("/es/seasons/2021");
  await page.getByRole("link", { name: /English/ }).click();
  await expect(page).toHaveURL(/\/en\/seasons\/2021$/);
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
});

test("la página no se desborda en horizontal", async ({ page }) => {
  for (const path of ["/es", "/es/races/1102/tyres", "/es/records"]) {
    await page.goto(path);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, path).toBeLessThanOrEqual(1);
  }
});
