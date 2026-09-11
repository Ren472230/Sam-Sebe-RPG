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

async function installNavigationDiagnostics(page: Page): Promise<void> {
  await page.evaluate(() => {
    const debugWindow = window as Window & {
      __navDebugInstalled?: boolean;
      __navKeyTrace?: string[];
      __navCanonicalMutations?: number;
    };
    debugWindow.__navKeyTrace = [];
    debugWindow.__navCanonicalMutations = 0;
    if (debugWindow.__navDebugInstalled) return;
    debugWindow.__navDebugInstalled = true;

    const pushKey = (phase: "down" | "up", event: KeyboardEvent): void => {
      const trace = debugWindow.__navKeyTrace ?? [];
      trace.push(`${phase}:${event.key.toLowerCase()}`);
      debugWindow.__navKeyTrace = trace.slice(-24);
    };
    window.addEventListener("keydown", (event) => pushKey("down", event), true);
    window.addEventListener("keyup", (event) => pushKey("up", event), true);

    new MutationObserver((mutations) => {
      const count = mutations.filter(
        (mutation) => mutation.type === "attributes" && mutation.attributeName === "data-canonical-location"
      ).length;
      debugWindow.__navCanonicalMutations = (debugWindow.__navCanonicalMutations ?? 0) + count;
    }).observe(document.body, { attributes: true, attributeFilter: ["data-canonical-location"] });
  });
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

async function interactionIsReady(
  page: Page,
  targetX: number,
  targetY: number,
  hintText: string,
  radius: number
): Promise<boolean> {
  const position = await playerPosition(page);
  const hint = await page.locator("#interaction-hint").textContent();
  return Number.isFinite(position.x)
    && Number.isFinite(position.y)
    && Math.hypot(targetX - position.x, targetY - position.y) <= radius
    && Boolean(hint?.includes(hintText));
}

async function moveAxisTowardInteraction(
  page: Page,
  axis: "x" | "y",
  axisTarget: number,
  targetX: number,
  targetY: number,
  hintText: string,
  stableInteractionRadius: number,
  timeout: number
): Promise<boolean> {
  if (await interactionIsReady(page, targetX, targetY, hintText, stableInteractionRadius)) return true;

  const start = await playerPosition(page);
  const value = start[axis];
  if (!Number.isFinite(value)) throw new Error(`player ${axis} position is unavailable`);

  const key: MovementKey = axis === "x"
    ? (value < axisTarget ? "d" : "a")
    : (value < axisTarget ? "s" : "w");
  const movingPositive = key === "d" || key === "s";
  let reached = start;

  await releaseMovementKeys(page);
  await page.keyboard.down(key);
  try {
    await page.waitForFunction(
      ({ watchedAxis, axisTarget, positive, targetX, targetY, hintText, radius }) => {
        const x = Number(document.body.dataset.playerX);
        const y = Number(document.body.dataset.playerY);
        const current = watchedAxis === "x" ? x : y;
        const hint = document.getElementById("interaction-hint")?.textContent ?? "";
        const ready = Number.isFinite(x)
          && Number.isFinite(y)
          && Math.hypot(targetX - x, targetY - y) <= radius
          && hint.includes(hintText);
        const crossedAxisTarget = Number.isFinite(current)
          && (positive ? current >= axisTarget : current <= axisTarget);
        return ready || crossedAxisTarget;
      },
      {
        watchedAxis: axis,
        axisTarget,
        positive: movingPositive,
        targetX,
        targetY,
        hintText,
        radius: stableInteractionRadius
      },
      { timeout, polling: "raf" }
    );
    reached = await playerPosition(page);
  } finally {
    await page.keyboard.up(key);
    await releaseMovementKeys(page);
  }

  const released = await playerPosition(page);
  await recordAxisTrace(page, { axis, target: axisTarget, reached, released });
  return interactionIsReady(page, targetX, targetY, hintText, stableInteractionRadius);
}

export async function moveTowardInteraction(
  page: Page,
  targetX: number,
  targetY: number,
  hintText: string,
  timeout = 12_000
): Promise<void> {
  await installNavigationDiagnostics(page);
  const hint = page.locator("#interaction-hint");
  const stableInteractionRadius = 60;
  const standoffX = Math.min(865, targetX + 45);

  await releaseMovementKeys(page);
  let ready = await moveAxisTowardInteraction(
    page,
    "y",
    targetY,
    targetX,
    targetY,
    hintText,
    stableInteractionRadius,
    timeout
  );
  if (!ready) {
    ready = await moveAxisTowardInteraction(
      page,
      "x",
      standoffX,
      targetX,
      targetY,
      hintText,
      stableInteractionRadius,
      timeout
    );
  }
  await releaseMovementKeys(page);
  await page.waitForTimeout(120);

  const settledPosition = await playerPosition(page);
  const settledDistance = Math.hypot(targetX - settledPosition.x, targetY - settledPosition.y);
  const settledHint = await hint.textContent();
  if (ready && settledDistance <= stableInteractionRadius && settledHint?.includes(hintText)) return;

  const diagnostics = await page.evaluate(() => {
    const debugWindow = window as Window & {
      __navKeyTrace?: string[];
      __navCanonicalMutations?: number;
    };
    return {
      canonicalLocation: document.body.dataset.canonicalLocation ?? null,
      renderedNpcIds: document.body.dataset.renderedNpcIds ?? null,
      renderedTavernNpcIds: document.body.dataset.renderedTavernNpcIds ?? null,
      movementTrace: document.body.dataset.movementTrace ?? null,
      keyTrace: debugWindow.__navKeyTrace ?? [],
      canonicalMutations: debugWindow.__navCanonicalMutations ?? 0
    };
  });
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