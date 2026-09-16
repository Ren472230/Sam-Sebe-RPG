import { expect, test } from "@playwright/test";

import { installBrowserDiagnostics } from "./helpers/browser-diagnostics";

test("844px coarse-pointer landscape keeps touch controls usable", async ({ browser }, testInfo) => {
  const context = await browser.newContext({
    viewport: { width: 844, height: 390 },
    hasTouch: true,
    isMobile: true
  });
  const page = await context.newPage();
  const diagnostics = installBrowserDiagnostics(page);

  try {
    await page.goto("/");
    await expect(page.locator("#hud")).toContainText("Цель:");

    const inputProfile = await page.evaluate(() => ({
      coarse: window.matchMedia("(any-pointer: coarse)").matches,
      viewportWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth
    }));
    expect(inputProfile.coarse).toBe(true);
    expect(inputProfile.documentWidth).toBeLessThanOrEqual(inputProfile.viewportWidth);
    expect(inputProfile.bodyWidth).toBeLessThanOrEqual(inputProfile.viewportWidth);

    const controls = page.locator("#touch-controls");
    const right = page.getByRole("button", { name: "Вправо", exact: true });
    const interact = page.getByRole("button", { name: "Взаимодействовать", exact: true });
    await expect(controls).toBeVisible();
    await expect(right).toBeVisible();
    await expect(interact).toBeVisible();

    await controls.scrollIntoViewIfNeeded();
    const geometry = await page.evaluate(() => {
      const controls = document.getElementById("touch-controls");
      const right = document.querySelector<HTMLButtonElement>("#touch-controls button[data-touch-key='D']");
      const interact = document.querySelector<HTMLButtonElement>("#touch-controls button[data-touch-key='E']");
      if (!controls || !right || !interact) return null;
      const controlsRect = controls.getBoundingClientRect();
      const rightRect = right.getBoundingClientRect();
      const interactRect = interact.getBoundingClientRect();
      return {
        controlsTop: controlsRect.top,
        controlsBottom: controlsRect.bottom,
        rightWidth: rightRect.width,
        rightHeight: rightRect.height,
        interactWidth: interactRect.width,
        interactHeight: interactRect.height,
        viewportHeight: window.innerHeight
      };
    });

    expect(geometry).not.toBeNull();
    expect(geometry!.controlsTop).toBeGreaterThanOrEqual(0);
    expect(geometry!.controlsBottom).toBeLessThanOrEqual(geometry!.viewportHeight);
    expect(geometry!.rightWidth).toBeGreaterThanOrEqual(48);
    expect(geometry!.rightHeight).toBeGreaterThanOrEqual(48);
    expect(geometry!.interactWidth).toBeGreaterThanOrEqual(48);
    expect(geometry!.interactHeight).toBeGreaterThanOrEqual(48);

    const before = Number(await page.locator("body").getAttribute("data-player-x"));
    await right.dispatchEvent("pointerdown", { pointerId: 41, pointerType: "touch", isPrimary: true });
    await expect(right).toHaveAttribute("data-pressed", "true");
    await page.waitForTimeout(180);
    await right.dispatchEvent("pointerup", { pointerId: 41, pointerType: "touch", isPrimary: true });
    await expect(right).toHaveAttribute("data-pressed", "false");
    await expect.poll(async () => Number(await page.locator("body").getAttribute("data-player-x"))).toBeGreaterThan(before);

    await page.screenshot({ path: "test-results/first-run-coarse-landscape-844.png", fullPage: true });
    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
    await context.close();
  }
});
