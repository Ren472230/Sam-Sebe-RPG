import { expect, test, type Page } from "@playwright/test";

type PlayerPosition = { x: number; y: number };
type ActionPayload = {
  success: boolean;
  code: string;
  summary: string;
  event_id: number | null;
  replayed: boolean;
};

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
  const hint = page.locator("#interaction-hint");
  const start = await playerPosition(page);
  // Firewood sits in a compact strip around x=112..260. Headless key-up latency can carry
  // the test past the strip, so sweep back toward its center instead of always walking left.
  const key = start.x < 186 ? "d" : "a";
  await releaseMovementKeys(page);
  await page.keyboard.down(key);
  try {
    // A repeated pickup may begin while the previous "pick up firewood" hint is still visible.
    // Require real movement first so an old hint can never trigger an empty E press.
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

async function verifyLivingWorldApi(page: Page): Promise<void> {
  const session = await page.request.post("/api/session", {
    data: { external_id: "browser-world-probe", name: "World Probe" }
  });
  expect(session.ok()).toBeTruthy();
  const { player_id: playerId } = await session.json() as { player_id: string };

  const waitOneResponse = await page.request.post("/api/action", {
    data: {
      player_id: playerId,
      action_type: "WAIT",
      modifiers: { ticks: 1 },
      external_id: "browser-wait-1"
    }
  });
  expect(waitOneResponse.ok()).toBeTruthy();
  const waitOne = await waitOneResponse.json() as ActionPayload;
  expect(waitOne.success).toBe(true);
  expect(waitOne.code).toBe("OK");
  expect(waitOne.summary).toBe("Waited 1 simulation tick(s).");
  expect(waitOne.replayed).toBe(false);

  const waitNineResponse = await page.request.post("/api/action", {
    data: {
      player_id: playerId,
      action_type: "WAIT",
      modifiers: { ticks: 9 },
      external_id: "browser-wait-9"
    }
  });
  expect(waitNineResponse.ok()).toBeTruthy();
  const waitNine = await waitNineResponse.json() as ActionPayload;
  expect(waitNine.success).toBe(true);
  expect(waitNine.code).toBe("OK");
  expect(waitNine.summary).toBe("Waited 9 simulation tick(s).");
  expect(waitNine.replayed).toBe(false);

  const replayResponse = await page.request.post("/api/action", {
    data: {
      player_id: playerId,
      action_type: "WAIT",
      modifiers: { ticks: 9 },
      external_id: "browser-wait-9"
    }
  });
  expect(replayResponse.ok()).toBeTruthy();
  const replay = await replayResponse.json() as ActionPayload;
  expect(replay.success).toBe(true);
  expect(replay.replayed).toBe(true);
  expect(replay.event_id).toBe(waitNine.event_id);
}

test("player can finish the firewood route with prototype art, persistent state, and live Living World", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/");
  const body = page.locator("body");
  await expect(body).toHaveAttribute("data-scene", "village");
  await expect(body).toHaveAttribute("data-art-mode", "prototype");
  await expect(body).toHaveAttribute("data-village-art", "prototype");
  await expect(body).toHaveAttribute("data-player-art", "prototype");
  await expect(body).toHaveAttribute("data-firewood-art", "prototype");
  await expect(page.locator("#hud")).toContainText("Workshop Yard");
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
  await expect(body).toHaveAttribute("data-tavern-art", "prototype");
  await expect(body).toHaveAttribute("data-player-art", "prototype");
  await expect(body).toHaveAttribute("data-oren-art", "prototype");
  await expect(page.locator("#hud")).toContainText("дрова доставлены ✓");
  await expect(page.locator("#hud")).toContainText("монеты 15");
  await expect(page.locator("#hud")).toContainText("доверие Орена 10");
  await page.screenshot({ path: "test-results/04-reloaded.png", fullPage: true });

  await verifyLivingWorldApi(page);
});
