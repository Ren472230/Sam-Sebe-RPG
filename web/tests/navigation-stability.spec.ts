import { expect, test } from "@playwright/test";

import {
  approachAndTalk,
  enterTavernSpatially,
  releaseMovementKeys
} from "./helpers/spatial-navigation";

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

test("canonical location change clears the previous NPC interaction immediately", async ({ page }) => {
  test.setTimeout(45_000);
  await page.goto("/");
  const body = page.locator("body");
  const hint = page.locator("#interaction-hint");

  await page.getByRole("button", { name: "Идти: площадь", exact: true }).click();
  await page.getByRole("button", { name: "Идти: река", exact: true }).click();
  await expect(body).toHaveAttribute("data-canonical-location", "river_edge");

  await approachAndTalk(page, 610, 410, "поговорить с Каспаром", "Каспар");
  await page.getByRole("button", { name: "Закрыть", exact: true }).click();
  await expect(hint).toContainText("поговорить с Каспаром", { timeout: 3_000 });

  await page.getByRole("button", { name: "Идти: площадь", exact: true }).click();
  await expect(body).toHaveAttribute("data-canonical-location", "village_square");

  await expect(hint).not.toContainText("поговорить с Каспаром", { timeout: 150 });
  await page.keyboard.press("e");
  await expect(page.locator("#dialogue")).toBeHidden();
});
