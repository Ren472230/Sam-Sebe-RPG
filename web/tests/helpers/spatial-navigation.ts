import { expect, type Page } from "@playwright/test";

export type PlayerPosition = { x: number; y: number };
type MovementKey = "w" | "a" | "s" | "d";

export async function playerPosition(page: Page): Promise<PlayerPosition> {
  return page.evaluate(() => ({
    x: Number(document.body.dataset.playerX),
    y: Number(document.body.dataset.playerY)
  }));
}

export async function releaseMovementKeys(page: Page): Promise<void> {
  for (const key of ["w", "a", "s", "d"] as const) await page.keyboard.up(key);
}

async function syncHeldMovementKeys(
  page: Page,
  held: Set<MovementKey>,
  desiredKeys: MovementKey[]
): Promise<void> {
  const desired = new Set(desiredKeys);

  for (const key of [...held]) {
    if (desired.has(key)) continue;
    await page.keyboard.up(key);
    held.delete(key);
  }

  for (const key of desiredKeys) {
    if (held.has(key)) continue;
    await page.keyboard.down(key);
    held.add(key);
  }
}

async function moveAxisIntoBand(
  page: Page,
  axis: "x" | "y",
  min: number,
  max: number,
  timeout = 12_000
): Promise<void> {
  const start = await playerPosition(page);
  const value = start[axis];
  if (Number.isFinite(value) && value >= min && value <= max) return;

  const key: MovementKey = axis === "x"
    ? (value < min ? "d" : "a")
    : (value < min ? "s" : "w");
  const movingPositive = key === "d" || key === "s";
  const threshold = movingPositive ? min : max;

  await releaseMovementKeys(page);
  await page.keyboard.down(key);
  try {
    await page.waitForFunction(
      ({ watchedAxis, target, positive }) => {
        const current = Number(
          watchedAxis === "x" ? document.body.dataset.playerX : document.body.dataset.playerY
        );
        return Number.isFinite(current) && (positive ? current >= target : current <= target);
      },
      { watchedAxis: axis, target: threshold, positive: movingPositive },
      { timeout, polling: "raf" }
    );
  } finally {
    await page.keyboard.up(key);
    await releaseMovementKeys(page);
  }

  const end = await playerPosition(page);
  if (end[axis] < min || end[axis] > max) {
    throw new Error(
      `player crossed ${axis} band [${min}, ${max}] before input could stop; last=${JSON.stringify(end)}`
    );
  }
}

export async function moveAxisTo(
  page: Page,
  axis: "x" | "y",
  target: number,
  tolerance = 12,
  timeout = 12_000
): Promise<void> {
  const started = Date.now();
  const held = new Set<MovementKey>();
  await releaseMovementKeys(page);

  try {
    while (Date.now() - started < timeout) {
      const position = await playerPosition(page);
      const value = position[axis];
      if (Number.isFinite(value) && Math.abs(value - target) <= tolerance) return;

      const key: MovementKey = axis === "x"
        ? (value < target ? "d" : "a")
        : (value < target ? "s" : "w");
      await syncHeldMovementKeys(page, held, [key]);
      await page.waitForTimeout(75);
    }
  } finally {
    await syncHeldMovementKeys(page, held, []);
    await releaseMovementKeys(page);
  }

  throw new Error(`player did not reach ${axis}=${target}; last=${JSON.stringify(await playerPosition(page))}`);
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
  const stableInteractionRadius = 60;
  const lowerLaneY = 455;
  // Approach NPCs from the right. For Mira this avoids the firewood cluster below
  // her; for Kaspar/Talen it avoids the well collision rectangle. 45px plus the
  // movement tolerance stays safely inside the 72–85px interaction radii.
  const standoffX = Math.min(865, targetX + 45);
  const remaining = (): number => Math.max(500, timeout - (Date.now() - started));

  await releaseMovementKeys(page);
  await moveAxisTo(page, "y", lowerLaneY, 12, remaining());
  await moveAxisTo(page, "x", standoffX, 12, remaining());
  await moveAxisTo(page, "y", targetY, 12, remaining());
  await releaseMovementKeys(page);
  await page.waitForTimeout(120);

  const settledPosition = await playerPosition(page);
  const settledDistance = Math.hypot(
    targetX - settledPosition.x,
    targetY - settledPosition.y
  );
  const settledHint = await hint.textContent();
  if (settledDistance <= stableInteractionRadius && settledHint?.includes(hintText)) return;

  const diagnostics = await page.evaluate(() => ({
    canonicalLocation: document.body.dataset.canonicalLocation ?? null,
    renderedNpcIds: document.body.dataset.renderedNpcIds ?? null,
    renderedTavernNpcIds: document.body.dataset.renderedTavernNpcIds ?? null
  }));
  throw new Error(
    `player did not reach stable interaction ${JSON.stringify(hintText)} near (${targetX}, ${targetY}); `
      + `last=${JSON.stringify(settledPosition)} distance=${Math.round(settledDistance)} `
      + `hint=${JSON.stringify(settledHint)} diagnostics=${JSON.stringify(diagnostics)}`
  );
}

export async function enterTavernSpatially(page: Page): Promise<void> {
  const hint = page.locator("#interaction-hint");

  // Preserve the proven human route around the village collision geometry:
  // travel east along the lower lane first, then approach the tavern door northward.
  await moveAxisIntoBand(page, "x", 790, 860, 20_000);

  if (!(await hint.textContent())?.includes("войти в таверну")) {
    await page.keyboard.down("w");
    try {
      await expect(hint).toContainText("войти в таверну", { timeout: 20_000 });
    } finally {
      await page.keyboard.up("w");
      await releaseMovementKeys(page);
    }
  }

  await expect(hint).toContainText("войти в таверну", { timeout: 3_000 });
  await page.keyboard.press("e");
  await expect(page.locator("body")).toHaveAttribute("data-scene", "tavern", { timeout: 10_000 });
}

export async function exitTavernSpatially(page: Page): Promise<void> {
  await moveAxisTo(page, "x", 110, 12, 12_000);
  await moveAxisTo(page, "y", 420, 12, 12_000);
  await expect(page.locator("#interaction-hint")).toContainText("выйти в деревню", { timeout: 3_000 });
  await page.keyboard.press("e");
  await expect(page.locator("body")).toHaveAttribute("data-scene", "village", { timeout: 10_000 });
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