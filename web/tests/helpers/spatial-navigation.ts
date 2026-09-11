import { expect, type Page } from "@playwright/test";

export type PlayerPosition = { x: number; y: number };
type MovementKey = "w" | "a" | "s" | "d";
type AxisTrace = {
  axis: "x" | "y";
  target: number;
  reached: PlayerPosition;
  released: PlayerPosition;
};

export async function playerPosition(page: Page): Promise<PlayerPosition> {
  return page.evaluate(() => ({
    x: Number(document.body.dataset.playerX),
    y: Number(document.body.dataset.playerY)
  }));
}

export async function releaseMovementKeys(page: Page): Promise<void> {
  for (const key of ["w", "a", "s", "d"] as const) await page.keyboard.up(key);
  await page.waitForTimeout(50);
}

async function recordAxisTrace(page: Page, trace: AxisTrace): Promise<void> {
  await page.evaluate((entry) => {
    const current = document.body.dataset.movementTrace;
    let parsed: unknown[] = [];
    if (current) {
      try {
        const value = JSON.parse(current);
        if (Array.isArray(value)) parsed = value;
      } catch {
        parsed = [];
      }
    }
    document.body.dataset.movementTrace = JSON.stringify([...parsed.slice(-7), entry]);
  }, trace);
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
  tolerance = 8,
  timeout = 10_000
): Promise<void> {
  const started = Date.now();
  let heldKey: MovementKey | null = null;
  let reached: PlayerPosition | null = null;
  await releaseMovementKeys(page);
  try {
    while (Date.now() - started < timeout) {
      const position = await playerPosition(page);
      const value = position[axis];
      if (Number.isFinite(value) && Math.abs(value - target) <= tolerance) {
        reached = position;
        break;
      }
      const key: MovementKey = axis === "x"
        ? (value < target ? "d" : "a")
        : (value < target ? "s" : "w");
      if (heldKey !== key) {
        if (heldKey) await page.keyboard.up(heldKey);
        await page.keyboard.down(key);
        heldKey = key;
      }
      await page.waitForTimeout(50);
    }
  } finally {
    if (heldKey) await page.keyboard.up(heldKey);
    await releaseMovementKeys(page);
  }

  const released = await playerPosition(page);
  if (reached) {
    await recordAxisTrace(page, { axis, target, reached, released });
    return;
  }
  throw new Error(`player did not reach ${axis}=${target}; last=${JSON.stringify(released)}`);
}

export async function moveTowardInteraction(
  page: Page,
  targetX: number,
  targetY: number,
  hintText: string,
  timeout = 12_000
): Promise<void> {
  const hint = page.locator("#interaction-hint");
  const stableInteractionRadius = 60;
  const standoffX = Math.min(865, targetX + 45);

  await releaseMovementKeys(page);
  await moveAxisTo(page, "y", targetY, 8, timeout);
  await moveAxisTo(page, "x", standoffX, 8, timeout);
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
    renderedTavernNpcIds: document.body.dataset.renderedTavernNpcIds ?? null,
    movementTrace: document.body.dataset.movementTrace ?? null
  }));
  throw new Error(
    `player did not reach stable interaction ${JSON.stringify(hintText)} near (${targetX}, ${targetY}); `
      + `last=${JSON.stringify(settledPosition)} distance=${Math.round(settledDistance)} `
      + `hint=${JSON.stringify(settledHint)} diagnostics=${JSON.stringify(diagnostics)}`
  );
}

export async function enterTavernSpatially(page: Page): Promise<void> {
  const hint = page.locator("#interaction-hint");
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