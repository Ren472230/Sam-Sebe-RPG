import { expect, test } from "@playwright/test";

import { enterTavernSpatially, releaseMovementKeys } from "./helpers/spatial-navigation";

test("spatial tavern entry survives a slower browser", async ({ page, context }) => {
  test.setTimeout(45_000);
  const cdp = await context.newCDPSession(page);

  try {
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
    await page.goto("/");
    await expect(page.locator("body")).toHaveAttribute("data-scene", "village");

    await enterTavernSpatially(page);
    await expect(page.locator("body")).toHaveAttribute("data-scene", "tavern", { timeout: 10_000 });
  } finally {
    await releaseMovementKeys(page);
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 }).catch(() => undefined);
  }
});
