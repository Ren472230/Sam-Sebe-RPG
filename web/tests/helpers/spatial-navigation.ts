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

async function tapMovementKey(page: Page, key: MovementKey): Promise<boolean> {
  const before = await playerPosition(page);
  await page.keyboard.press(key, { delay: 120 });
  const after = await playerPosition(page);
  return after.x !== before.x || after.y !== before.y;
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
  const coordinateTolerance = 3;
  const started = Date.now();
  let snapshot = await interactionSnapshot(page, targetX, targetY, hintText, stableInteractionRadius);
  await releaseMovementKeys(page);

  while (Date.now() - started < timeout) {
    if (snapshot.ready) return;

    const dx = targetX - snapshot.position.x;
    const dy = targetY - snapshot.position.y;
    const candidates: Array<{ key: MovementKey; error: number }> = [];
    if (Math.abs(dx) > coordinateTolerance) {
      candidates.push({ key: dx > 0 ? "d" : "a", error: Math.abs(dx) });
    }
    if (Math.abs(dy) > coordinateTolerance) {
      candidates.push({ key: dy > 0 ? "s" : "w", error: Math.abs(dy) });
    }
    candidates.sort((left, right) => right.error - left.error);

    if (candidates.length === 0) {
      await releaseMovementKeys(page);
      await page.waitForTimeout(700);
      snapshot = await interactionSnapshot(page, targetX, targetY, hintText, stableInteractionRadius);
      if (snapshot.ready) return;
      break;
    }

    let moved = false;
    for (const candidate of candidates) {
      moved = await tapMovementKey(page, candidate.key);
      snapshot = await interactionSnapshot(page, targetX, targetY, hintText, stableInteractionRadius);
      if (snapshot.ready) return;
      if (moved) break;
    }
    if (!moved) await page.waitForTimeout(50);
  }

  await releaseMovementKeys(page);
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
  await moveAxisOneWayTo(page, "x", 790);
  await moveWithConcurrentKeysUntilHint(page, ["w"], "войти в таверну", 20_000);
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