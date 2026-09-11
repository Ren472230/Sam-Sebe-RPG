import { expect, test } from "@playwright/test";

import { moveTowardInteraction, releaseMovementKeys } from "./helpers/spatial-navigation";

test("spatial navigation reaches the tavern interaction under a slower browser", async ({ page, context }) => {
  test.setTimeout(45_000);
  const cdp = await context.newCDPSession(page);

  try {
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
    await page.goto("/");
    await expect(page.locator("body")).toHaveAttribute("data-scene", "village");

    await moveTowardInteraction(page, 825, 365, "войти в таверну", 12_000);
    await expect(page.locator("#interaction-hint")).toContainText("войти в таверну");

    await page.keyboard.press("e");
    await expect(page.locator("body")).toHaveAttribute("data-scene", "tavern", { timeout: 10_000 });
  } finally {
    await releaseMovementKeys(page);
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 }).catch(() => undefined);
  }
});
