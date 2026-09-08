import { expect, test } from "@playwright/test";

import { installBrowserDiagnostics } from "./helpers/browser-diagnostics";


test("normal mode gives the player a localized immediate goal and a presentation-ready title", async ({ page }, testInfo) => {
  const diagnostics = installBrowserDiagnostics(page);
  try {
    await page.goto("/");
    const hud = page.locator("#hud");

    await expect(page).toHaveTitle("Сам-себе-RPG");
    await expect(hud).toContainText("Цель:");
    await expect(hud).not.toContainText(/Workshop Yard|Village Square|River Edge|The Wayfarer's Hearth/);
    await expect(hud).toContainText("монеты");

    await page.screenshot({ path: "test-results/first-run-clarity.png", fullPage: true });
    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
  }
});


test("390px viewport keeps touch controls reachable without a keyboard", async ({ page }, testInfo) => {
  const diagnostics = installBrowserDiagnostics(page);
  try {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    await expect(page.locator("#hud")).toContainText("Цель:");

    const layout = await page.evaluate(() => ({
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth
    }));

    expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewportWidth);
    expect(layout.bodyWidth).toBeLessThanOrEqual(layout.viewportWidth);
    await expect(page.locator("#game canvas")).toBeVisible();
    await expect(page.getByRole("button", { name: "Подождать 1 шаг", exact: true })).toBeVisible();

    const right = page.getByRole("button", { name: "Вправо", exact: true });
    const interact = page.getByRole("button", { name: "Взаимодействовать", exact: true });
    await expect(right).toBeVisible();
    await expect(interact).toBeVisible();

    const hint = page.locator("#interaction-hint");
    await expect(hint).toContainText("Экранные кнопки – движение · Действие – взаимодействие");
    await expect(hint).not.toContainText(/WASD|E —/);

    const controls = await page.evaluate(() => {
      const element = document.getElementById("touch-controls");
      if (!element) return null;
      const rect = element.getBoundingClientRect();
      return { top: rect.top, bottom: rect.bottom };
    });
    expect(controls).not.toBeNull();
    expect(controls!.top).toBeGreaterThanOrEqual(0);
    expect(controls!.bottom).toBeLessThanOrEqual(layout.viewportHeight);

    const before = Number(await page.locator("body").getAttribute("data-player-x"));
    await right.dispatchEvent("pointerdown", { pointerId: 1, pointerType: "touch", isPrimary: true });
    await page.waitForTimeout(180);
    await right.dispatchEvent("pointerup", { pointerId: 1, pointerType: "touch", isPrimary: true });
    await expect.poll(async () => Number(await page.locator("body").getAttribute("data-player-x"))).toBeGreaterThan(before);

    await page.screenshot({ path: "test-results/first-run-mobile-390.png", fullPage: true });
    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
  }
});
