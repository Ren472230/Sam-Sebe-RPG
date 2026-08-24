import { expect, test, type Page } from "@playwright/test";

type PlayerPosition = { x: number; y: number };

async function playerPosition(page: Page): Promise<PlayerPosition> {
  return page.evaluate(() => ({
    x: Number(document.body.dataset.playerX),
    y: Number(document.body.dataset.playerY)
  }));
}

async function releaseMovementKeys(page: Page): Promise<void> {
  for (const key of ["w", "a", "s", "d"]) {
    await page.keyboard.up(key);
  }
  await page.waitForTimeout(60);
}

async function moveAxisTo(
  page: Page,
  axis: "x" | "y",
  target: number,
  tolerance = 12,
  timeout = 12_000
): Promise<void> {
  const started = Date.now();
  let heldKey: string | null = null;
  await releaseMovementKeys(page);
  try {
    while (Date.now() - started < timeout) {
      const position = await playerPosition(page);
      const value = position[axis];
      if (Number.isFinite(value) && Math.abs(value - target) <= tolerance) return;
      const key = axis === "x"
        ? (value < target ? "d" : "a")
        : (value < target ? "s" : "w");
      if (heldKey !== key) {
        if (heldKey) await page.keyboard.up(heldKey);
        await page.keyboard.down(key);
        heldKey = key;
      }
      await page.waitForTimeout(100);
    }
  } finally {
    if (heldKey) await page.keyboard.up(heldKey);
    await releaseMovementKeys(page);
  }
  throw new Error(`player did not reach ${axis}=${target}; last=${JSON.stringify(await playerPosition(page))}`);
}

async function moveAndInteractWhenHint(
  page: Page,
  keys: string[],
  hintText: string,
  timeout = 10_000
): Promise<void> {
  const hint = page.locator("#interaction-hint");
  await releaseMovementKeys(page);
  for (const key of keys) await page.keyboard.down(key);
  try {
    await expect(hint).toContainText(hintText, { timeout });
    await page.keyboard.press("e");
  } finally {
    for (const key of keys) await page.keyboard.up(key);
    await releaseMovementKeys(page);
  }
}

async function enterTavernFromVillage(page: Page): Promise<void> {
  // Go to the right edge first, then approach the door diagonally from the walkable road below.
  await moveAxisTo(page, "x", 936, 4);
  await moveAndInteractWhenHint(page, ["w", "a"], "войти в таверну");
  await expect(page.locator("body")).toHaveAttribute("data-scene", "tavern");
}

async function approachOren(page: Page): Promise<void> {
  await moveAndInteractWhenHint(page, ["w", "d"], "поговорить с Ореном");
  await expect(page.locator("#dialogue")).toBeVisible();
  await expect(page.locator("#dialogue h2")).toHaveText("Орен");
}

async function leaveTavern(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Закрыть" }).click().catch(() => undefined);
  await moveAndInteractWhenHint(page, ["s", "a"], "выйти в деревню");
  await expect(page.locator("body")).toHaveAttribute("data-scene", "village");
}

async function collectOneFirewood(page: Page, expectedCount: number): Promise<void> {
  await moveAndInteractWhenHint(page, ["a"], "подобрать дрова", 10_000);
  await expect(page.locator("#hud")).toContainText(`дрова ${expectedCount}/5`);
}

test("player can finish the critical firewood route in the real browser and reload into canonical scene", async ({ page }) => {
  test.setTimeout(120_000);
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
