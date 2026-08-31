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
  // Wait for the newly-created VillageScene to publish its own spawn coordinates.
  // Without this barrier a stale TavernScene coordinate can send the next sweep the wrong way.
  await expect.poll(async () => {
    const position = await playerPosition(page);
    return Math.abs(position.x - 430) <= 20 && Math.abs(position.y - 455) <= 30;
  }, { timeout: 5_000 }).toBe(true);
}

async function collectOneFirewood(page: Page, expectedCount: number): Promise<void> {
  const hint = page.locator("#interaction-hint");
  const start = await playerPosition(page);
  const key = start.x < 186 ? "d" : "a";
  await releaseMovementKeys(page);
  await page.keyboard.down(key);
  try {
    await expect.poll(async () => {
      const current = await playerPosition(page);
      return key === "a" ? start.x - current.x : current.x - start.x;
    }, { timeout: 5_000 }).toBeGreaterThan(12);
    await expect(hint).toContainText("подобрать дрова", { timeout: 10_000 });
    await page.keyboard.press("e");
  } finally {
    await page.keyboard.up(key);
    await releaseMovementKeys(page);
  }
  await expect(page.locator("#hud")).toContainText(`дрова ${expectedCount}/5`);
}

async function clickWorldAction(page: Page, name: string): Promise<void> {
  const button = page.locator("#world-panel").getByRole("button", { name });
  await expect(button).toBeVisible();
  await button.click();
}

test("player can finish Oren quest, observe Living World, intervene, and reload persistent state", async ({ page }) => {
  test.setTimeout(150_000);
  await page.goto("/");
  const body = page.locator("body");
  const worldPanel = page.locator("#world-panel");
  await expect(body).toHaveAttribute("data-scene", "village");
  await expect(body).toHaveAttribute("data-art-mode", "prototype");
  await expect(body).toHaveAttribute("data-village-art", "prototype");
  await expect(body).toHaveAttribute("data-player-art", "prototype");
  await expect(body).toHaveAttribute("data-firewood-art", "prototype");
  await expect(page.locator("#hud")).toContainText("Workshop Yard");
  await expect(worldPanel).toBeVisible();
  await expect(worldPanel).toContainText("Живой мир");
  await expect(worldPanel).toHaveAttribute("data-world-tick", "0");
  await page.screenshot({ path: "test-results/01-village.png", fullPage: true });

  await enterTavernFromVillage(page);
  await expect(body).toHaveAttribute("data-art-mode", "prototype");
  await expect(body).toHaveAttribute("data-tavern-art", "prototype");
  await expect(body).toHaveAttribute("data-player-art", "prototype");
  await expect(body).toHaveAttribute("data-oren-art", "prototype");
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
  await expect(body).toHaveAttribute("data-scene", "tavern");
  await expect(body).toHaveAttribute("data-art-mode", "prototype");
  await expect(page.locator("#hud")).toContainText("дрова доставлены ✓");
  await expect(page.locator("#hud")).toContainText("монеты 15");
  await expect(page.locator("#hud")).toContainText("доверие Орена 10");
  await page.screenshot({ path: "test-results/04-reloaded.png", fullPage: true });

  // Living World / Player Intervention through the actual player-facing browser UI.
  await leaveTavern(page);
  await clickWorldAction(page, "К мастерской");
  await expect(page.locator("#hud")).toContainText("Workshop Yard");

  await clickWorldAction(page, "Подождать 4 хода");
  await expect(worldPanel).toHaveAttribute("data-world-tick", "4");
  await expect(worldPanel).toHaveAttribute("data-mira-status", "working");
  await expect(worldPanel).toHaveAttribute("data-mira-wood-stock", "0");

  await clickWorldAction(page, "Подождать 1 ход");
  await expect(worldPanel).toHaveAttribute("data-world-tick", "5");
  await expect(worldPanel).toHaveAttribute("data-mira-status", "needs_wood");
  await expect(worldPanel).toHaveAttribute("data-kaspar-status", "collecting_wood");
  await expect(worldPanel).toHaveAttribute("data-kaspar-carrying", "false");
  await page.screenshot({ path: "test-results/05-world-request.png", fullPage: true });

  await clickWorldAction(page, "На площадь");
  await clickWorldAction(page, "К реке");
  await expect(page.locator("#hud")).toContainText("River Edge");
  await clickWorldAction(page, "Забрать корягу");
  await expect(worldPanel).toHaveAttribute("data-has-driftwood", "true");

  // Kaspar reaches the same resource but cannot fabricate or steal a second copy.
  await clickWorldAction(page, "Подождать 1 ход");
  await expect(worldPanel).toHaveAttribute("data-kaspar-status", "collecting_wood");
  await expect(worldPanel).toHaveAttribute("data-kaspar-carrying", "false");

  await clickWorldAction(page, "На площадь");
  await clickWorldAction(page, "К мастерской");
  await clickWorldAction(page, "Отдать корягу Мире");
  await expect(worldPanel).toHaveAttribute("data-has-driftwood", "false");
  await expect(worldPanel).toHaveAttribute("data-mira-status", "working");
  await expect(worldPanel).toHaveAttribute("data-mira-wood-stock", "1");
  await expect(worldPanel).toHaveAttribute("data-kaspar-status", "schedule");
  await page.screenshot({ path: "test-results/06-intervention-complete.png", fullPage: true });

  await page.reload();
  await expect(body).toHaveAttribute("data-scene", "village");
  await expect(page.locator("#hud")).toContainText("дрова доставлены ✓");
  await expect(worldPanel).toHaveAttribute("data-world-tick", "6");
  await expect(worldPanel).toHaveAttribute("data-has-driftwood", "false");
  await expect(worldPanel).toHaveAttribute("data-mira-status", "working");
  await expect(worldPanel).toHaveAttribute("data-mira-wood-stock", "1");
  await expect(worldPanel).toHaveAttribute("data-kaspar-status", "schedule");
  await page.screenshot({ path: "test-results/07-intervention-reloaded.png", fullPage: true });
});
