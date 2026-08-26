import { expect, test } from "@playwright/test";

test("persisted reload has no critical browser console errors", async ({ page }) => {
  const critical: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") critical.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => critical.push(`pageerror: ${error.message}`));

  await page.goto("/");
  await expect(page.locator("body")).toHaveAttribute("data-scene", "tavern");
  await expect(page.locator("#hud")).toContainText("дрова доставлены ✓");
  await expect(page.locator("#hud")).toContainText("монеты 15");
  await expect(page.locator("#hud")).toContainText("доверие Орена 10");
  await page.waitForTimeout(750);

  expect(critical).toEqual([]);
});
