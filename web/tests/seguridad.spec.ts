import { expect, test } from "@playwright/test";

test("las páginas llevan las cabeceras de seguridad", async ({ request }) => {
  const response = await request.get("/es");
  expect(response.ok()).toBe(true);
  const headers = response.headers();
  expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
  expect(headers["x-powered-by"]).toBeUndefined();
});

test("los gráficos no infringen la política de seguridad de contenido", async ({ page }) => {
  const violations: string[] = [];
  page.on("console", (message) => {
    if (message.text().includes("Content Security Policy")) violations.push(message.text());
  });
  // El evento lo lanza el navegador en la propia página; se recoge antes de que cargue nada.
  await page.addInitScript(() => {
    const seen: string[] = [];
    (window as unknown as { __cspViolations: string[] }).__cspViolations = seen;
    document.addEventListener("securitypolicyviolation", (event) => {
      seen.push(`${event.violatedDirective}: ${event.blockedURI}`);
    });
  });
  for (const path of ["/es/races/1102/lap-chart", "/es/races/1102/telemetry", "/es/seasons/2021"]) {
    await page.goto(path);
    await expect(page.getByRole("img").first()).toBeVisible();
    const events = await page.evaluate(
      () => (window as unknown as { __cspViolations: string[] }).__cspViolations,
    );
    violations.push(...events.map((event) => `${path} ${event}`));
  }
  expect(violations).toEqual([]);
});
