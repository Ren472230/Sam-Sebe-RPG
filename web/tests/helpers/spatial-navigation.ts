import { expect, type Page } from "@playwright/test";

export type PlayerPosition = { x: number; y: number };

export async function playerPosition(page: Page): Promise<PlayerPosition> {
  return page.evaluate(() => ({
    x: Number(document.body.dataset.playerX),
    y: Number(document.body.dataset.playerY)
  }));
}

export async function releaseMovementKeys(page: Page): Promise<void> {
  for (const key of ["w", "a", "s", "d"]) await page.keyboard.up(key);
  await page.waitForTimeout(50);
}

export async function moveTowardInteraction(
  page: Page,
  targetX: number,
  targetY: number,
  hintText: string,
  timeout = 12_000
): Promise<void> {
  const started = Date.now();
  const hint = page.locator("#interaction-hint");
  await releaseMovementKeys(page);

  while (Date.now() - started < timeout) {
    if ((await hint.textContent())?.includes(hintText)) return;

    const position = await playerPosition(page);
    const dx = targetX - position.x;
    const dy = targetY - position.y;
    const horizontal = dx >= 0 ? "d" : "a";
    const vertical = dy >= 0 ? "s" : "w";
    const keys = Math.abs(dx) >= Math.abs(dy)
      ? [horizontal, vertical]
      : [vertical, horizontal];

    for (const key of keys) {
      await page.keyboard.down(key);
      await page.waitForTimeout(70);
      await page.keyboard.up(key);
      await page.waitForTimeout(35);
      if ((await hint.textContent())?.includes(hintText)) return;
    }
  }

  throw new Error(
    `player did not reach interaction ${JSON.stringify(hintText)} near (${targetX}, ${targetY}); last=${JSON.stringify(await playerPosition(page))}`
  );
}

export async function approachAndTalk(
  page: Page,
  targetX: number,
  targetY: number,
  hintText: string,
  heading: string
): Promise<void> {
  await moveTowardInteraction(page, targetX, targetY, hintText);
  await expect(page.locator("#interaction-hint")).toContainText(hintText, { timeout: 3_000 });
  await page.keyboard.press("e");
  await expect(page.locator("#dialogue")).toBeVisible({ timeout: 5_000 });
  await expect(page.locator("#dialogue h2")).toHaveText(heading);
}
