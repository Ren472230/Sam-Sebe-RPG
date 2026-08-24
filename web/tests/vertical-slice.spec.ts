import { expect, test, type Page } from "@playwright/test";

async function hold(page: Page, key: string, milliseconds: number): Promise<void> {
  await page.keyboard.down(key);
  await page.waitForTimeout(milliseconds);
  await page.keyboard.up(key);
}

async function holdUntilHint(page: Page, key: string, text: string, timeout = 4_000): Promise<void> {
  const hint = page.locator("#interaction-hint");
  await page.keyboard.down(key);
  try {
    await expect(hint).toContainText(text, { timeout });
  } finally {
    await page.keyboard.up(key);
  }
}

async function enterTavernFromVillage(page: Page): Promise<void> {
  await hold(page, "d", 650);
  await hold(page, "w", 720);
  await holdUntilHint(page, "d", "войти в таверну");
  await page.keyboard.press("e");
  await expect(page.locator("body")).toHaveAttribute("data-scene", "tavern");
}

async function approachOren(page: Page): Promise<void> {
  await hold(page, "w", 470);
  await holdUntilHint(page, "d", "поговорить с Ореном");
  await page.keyboard.press("e");
  await expect(page.locator("#dialogue")).toBeVisible();
  await expect(page.locator("#dialogue h2")).toHaveText("Орен");
}

async function leaveTavern(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Закрыть" }).click().catch(() => undefined);
  await hold(page, "s", 520);
  await holdUntilHint(page, "a", "выйти в деревню");
  await page.keyboard.press("e");
  await expect(page.locator("body")).toHaveAttribute("data-scene", "village");
}

async function collectOneFirewood(page: Page, expectedCount: number): Promise<void> {
  await holdUntilHint(page, "a", "подобрать дрова", 5_000);
  await page.keyboard.press("e");
  await expect(page.locator("#hud")).toContainText(`дрова ${expectedCount}/5`);
}

test("player can finish the critical firewood route in the real browser and reload into canonical scene", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("body")).toHaveAttribute("data-scene", "village");
  await expect(page.locator("#hud")).toContainText("Workshop Yard");
  await page.screenshot({ path: "test-results/01-village.png", fullPage: true });

  await enterTavernFromVillage(page);
  await approachOren(page);
  await expect(page.getByRole("button", { name: "Взяться за дрова" })).toBeVisible();
  await page.screenshot({ path: "test-results/02-oren-offer.png", fullPage: true });
  await page.getByRole("button", { name: "Взяться за дрова" }).click();
  await expect(page.locator("#hud")).toContainText("дрова 0/5");

  await leaveTavern(page);
  for (let count = 1; count <= 4; count += 1) {
    await collectOneFirewood(page, count);
  }

  await enterTavernFromVillage(page);
  await approachOren(page);
  await page.getByRole("button", { name: "Передать дрова" }).click();
  await expect(page.locator("#dialogue")).toContainText("Oren still needs 1 more firewood.");

  await leaveTavern(page);
  await collectOneFirewood(page, 5);

  await enterTavernFromVillage(page);
  await approachOren(page);
  await page.getByRole("button", { name: "Передать дрова" }).click();
  await expect(page.locator("#hud")).toContainText("дрова доставлены ✓");
  await expect(page.locator("#hud")).toContainText("монеты 15");
  await expect(page.locator("#hud")).toContainText("доверие Орена 10");
  await expect(page.locator("#dialogue")).toContainText("помню, что ты выручил меня");
  await page.screenshot({ path: "test-results/03-completed.png", fullPage: true });

  await page.reload();
  await expect(page.locator("body")).toHaveAttribute("data-scene", "tavern");
  await expect(page.locator("#hud")).toContainText("дрова доставлены ✓");
  await expect(page.locator("#hud")).toContainText("монеты 15");
  await expect(page.locator("#hud")).toContainText("доверие Орена 10");
  await page.screenshot({ path: "test-results/04-reloaded.png", fullPage: true });
});
