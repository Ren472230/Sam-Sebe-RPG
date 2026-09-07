import { expect, test } from "@playwright/test";

import { installBrowserDiagnostics } from "./helpers/browser-diagnostics";


test("normal mode gives the player a localized immediate goal", async ({ page }, testInfo) => {
  const diagnostics = installBrowserDiagnostics(page);
  try {
    await page.goto("/");
    const hud = page.locator("#hud");

    await expect(hud).toContainText("Цель:");
    await expect(hud).not.toContainText(/Workshop Yard|Village Square|River Edge|The Wayfarer's Hearth/);
    await expect(hud).toContainText("монеты");

    await page.screenshot({ path: "test-results/first-run-clarity.png", fullPage: true });
    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
  }
});
