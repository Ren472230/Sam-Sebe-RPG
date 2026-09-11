import { expect, type Page } from "@playwright/test";

export type PlayerPosition = { x: number; y: number };
type MovementKey = "w" | "a" | "s" | "d";
type AxisTrace = {
  axis: "x" | "y";
  target: number;
  reached: PlayerPosition;
  released: PlayerPosition;
};

type InteractionSnapshot = {
  position: PlayerPosition;
  hint: string;
  ready: boolean;
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

async function moveAxisOneWayTo(
  page: Page,
  axis: "x" | "y",
  target: number,
  timeout = 8_000
): Promise<void> {
  await installNavigationDiagnostics(page);
  let position = await playerPosition(page);
  const start = position;
  const value = position[axis];
  if (!Number.isFinite(value) || value === target) return;

  const key: MovementKey = axis === "x"
    ? (value < target ? "d" : "a")
    : (value < target ? "s" : "w");
  const started = Date.now();
  let reached: PlayerPosition | null = null;

  await releaseMovementKeys(page);
  await page.keyboard.down(key);
  try {
    while (Date.now() - started < timeout) {
      position = await playerPosition(page);
      const current = position[axis];
      const crossed = key === "d" || key === "s" ? current >= target : current <= target;
      if (crossed) {
        reached = position;
        break;
      }
      await page.waitForTimeout(25);
    }
  } finally {
    await page.keyboard.up(key);
    await releaseMovementKeys(page);
  }

  const released = await playerPosition(page);
  if (!reached) {
    throw new Error(
      `one-way ${key} movement did not reach ${axis}=${target}; `
        + `start=${JSON.stringify(start)} end=${JSON.stringify(released)}`
    );
  }
  await recordAxisTrace(page, { axis, target, reached, released });
}

async function interactionSnapshot(
  page: Page,
  targetX: number,
  targetY: number,
  hintText: string,
  radius: number
): Promise<InteractionSnapshot> {
  return page.evaluate(({ targetX, targetY, hintText, radius }) => {
    const position = {
      x: Number(document.body.dataset.playerX),
      y: Number(document.body.dataset.playerY)
    };
    const hint = document.getElementById("interaction-hint")?.textContent ?? "";
    return {
      position,
      hint,
      ready: Number.isFinite(position.x)
        && Number.isFinite(position.y)
        && Math.hypot(targetX - position.x, targetY - position.y) <= radius
        && hint.includes(hintText)
    };
  }, { targetX, targetY, hintText, radius });
}

function movementKeyForBand(
  value: number,
  min: number,
  max: number,
  negative: MovementKey,
  positive: MovementKey
): MovementKey | null {
  if (value < min) return positive;
  if (value > max) return negative;
  return null;
}

function crossedBand(
  key: MovementKey,
  value: number,
  min: number,
  max: number
): boolean {
  if (key === "d" || key === "s") return value >= min;
  return value <= max;
}

export async function moveTowardInteraction(
  page: Page,
  targetX: number,
  targetY: number,
  hintText: string,
  timeout = 12_000
): Promise<void> {
  await installNavigationDiagnostics(page);
  const stableInteractionRadius = 68;
  const axisMargin = 0;
  const started = Date.now();
  let snapshot = await interactionSnapshot(page, targetX, targetY, hintText, stableInteractionRadius);
  if (snapshot.ready) return;

  const xMin = targetX - axisMargin;
  const xMax = targetX + axisMargin;
  const yMin = targetY - axisMargin;
  const yMax = targetY + axisMargin;
  let xKey = movementKeyForBand(snapshot.position.x, xMin, xMax, "a", "d");
  let yKey = movementKeyForBand(snapshot.position.y, yMin, yMax, "w", "s");

  await releaseMovementKeys(page);
  if (xKey) await page.keyboard.down(xKey);
  if (yKey) await page.keyboard.down(yKey);

  try {
    while (Date.now() - started < timeout) {
      snapshot = await interactionSnapshot(page, targetX, targetY, hintText, stableInteractionRadius);
      if (snapshot.ready) break;

      if (xKey && crossedBand(xKey, snapshot.position.x, xMin, xMax)) {
        await page.keyboard.up(xKey);
        xKey = null;
      }
      if (yKey && crossedBand(yKey, snapshot.position.y, yMin, yMax)) {
        await page.keyboard.up(yKey);
        yKey = null;
      }
      if (!xKey && !yKey) {
        await page.waitForTimeout(50);
        snapshot = await interactionSnapshot(page, targetX, targetY, hintText, stableInteractionRadius);
        break;
      }
      await page.waitForTimeout(25);
    }
  } finally {
    if (xKey) await page.keyboard.up(xKey);
    if (yKey) await page.keyboard.up(yKey);
    await releaseMovementKeys(page);
  }

  snapshot = await interactionSnapshot(page, targetX, targetY, hintText, stableInteractionRadius);
  if (snapshot.ready) return;

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
  const gap = Math.hypot(targetX - snapshot.position.x, targetY - snapshot.position.y);
  throw new Error(
    `player did not reach stable interaction ${JSON.stringify(hintText)} near (${targetX}, ${targetY}); `
      + `last=${JSON.stringify(snapshot.position)} distance=${Math.round(gap)} `
      + `hint=${JSON.stringify(snapshot.hint)} diagnostics=${JSON.stringify(diagnostics)}`
  );
}

async function moveWithConcurrentKeysUntilHint(
  page: Page,
  keys: MovementKey[],
  hintText: string,
  timeout: number
): Promise<void> {
  await installNavigationDiagnostics(page);
  const hint = page.locator("#interaction-hint");
  if ((await hint.textContent())?.includes(hintText)) return;

  const startedAt = await playerPosition(page);
  await releaseMovementKeys(page);
  for (const key of keys) await page.keyboard.down(key);
  try {
    await expect(hint).toContainText(hintText, { timeout });
  } catch (error) {
    const endedAt = await playerPosition(page);
    const diagnostics = await page.evaluate(() => {
      const debugWindow = window as Window & {
        __navKeyTrace?: string[];
        __navCanonicalMutations?: number;
      };
      return {
        scene: document.body.dataset.scene ?? null,
        canonicalLocation: document.body.dataset.canonicalLocation ?? null,
        movementTrace: document.body.dataset.movementTrace ?? null,
        keyTrace: debugWindow.__navKeyTrace ?? [],
        canonicalMutations: debugWindow.__navCanonicalMutations ?? 0,
        hint: document.getElementById("interaction-hint")?.textContent ?? ""
      };
    });
    throw new Error(
      `movement ${keys.join("+")} did not reach ${JSON.stringify(hintText)}; `
        + `start=${JSON.stringify(startedAt)} end=${JSON.stringify(endedAt)} `
        + `diagnostics=${JSON.stringify(diagnostics)} cause=${error instanceof Error ? error.message : String(error)}`
    );
  } finally {
    for (const key of keys) await page.keyboard.up(key);
    await releaseMovementKeys(page);
  }
}

export async function enterTavernSpatially(page: Page): Promise<void> {
  const hint = page.locator("#interaction-hint");
  await moveAxisOneWayTo(page, "y", 455);
  await moveAxisOneWayTo(page, "x", 600);
  await moveWithConcurrentKeysUntilHint(page, ["d", "w"], "войти в таверну", 20_000);
  await expect(hint).toContainText("войти в таверну", { timeout: 3_000 });
  await page.keyboard.press("e");
  await expect(page.locator("body")).toHaveAttribute("data-scene", "tavern", { timeout: 10_000 });
}

export async function exitTavernSpatially(page: Page): Promise<void> {
  const hint = page.locator("#interaction-hint");
  await moveWithConcurrentKeysUntilHint(page, ["a", "s"], "выйти в деревню", 20_000);
  await expect(hint).toContainText("выйти в деревню", { timeout: 3_000 });
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