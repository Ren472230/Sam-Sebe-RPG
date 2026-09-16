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
  hintReady: boolean;
};

const MOVEMENT_KEYS = ["w", "a", "s", "d"] as const;
const VILLAGE_WELL_CLEAR_X = 560;
const VILLAGE_LOWER_LANE_Y = 455;
const STEERING_PULSE_MS = 80;
const CORRIDOR_PULSE_MS = 180;
const TARGET_TOLERANCE = 7;
const INTERACTION_AXIS_MARGIN = 30;
const TAVERN_SAFE_X_MARGIN = 20;
const TAVERN_SAFE_Y_MIN = 320;
const TAVERN_SAFE_Y_MAX = 333;

export async function playerPosition(page: Page): Promise<PlayerPosition> {
  return page.evaluate(() => ({
    x: Number(document.body.dataset.playerX),
    y: Number(document.body.dataset.playerY)
  }));
}

async function waitForBrowserFrame(page: Page): Promise<void> {
  if (page.isClosed()) return;
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => resolve())));
}

async function playerPositionAfterBrowserFrame(page: Page): Promise<PlayerPosition> {
  return page.evaluate(() => new Promise<PlayerPosition>((resolve) => {
    requestAnimationFrame(() => resolve({
      x: Number(document.body.dataset.playerX),
      y: Number(document.body.dataset.playerY)
    }));
  }));
}

export async function releaseMovementKeys(page: Page): Promise<void> {
  if (page.isClosed()) return;
  for (const key of MOVEMENT_KEYS) {
    try {
      await page.keyboard.up(key);
    } catch (error) {
      if (page.isClosed()) return;
      throw error;
    }
  }
}

async function installNavigationDiagnostics(page: Page): Promise<void> {
  await page.evaluate(() => {
    const debugWindow = window as Window & {
      __navDebugInstalled?: boolean;
      __navKeyTrace?: string[];
      __navCanonicalMutations?: number;
    };
    if (debugWindow.__navDebugInstalled) return;
    debugWindow.__navDebugInstalled = true;
    debugWindow.__navKeyTrace = [];
    debugWindow.__navCanonicalMutations = 0;

    const pushKey = (phase: "down" | "up", event: KeyboardEvent): void => {
      const trace = debugWindow.__navKeyTrace ?? [];
      trace.push(`${phase}:${event.key.toLowerCase()}`);
      debugWindow.__navKeyTrace = trace.slice(-32);
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
  if (page.isClosed()) return;
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
    document.body.dataset.movementTrace = JSON.stringify([...parsed.slice(-11), entry]);
  }, trace);
}

async function interactionSnapshot(page: Page, hintText: string): Promise<InteractionSnapshot> {
  return page.evaluate(({ hintText }) => {
    const hint = document.getElementById("interaction-hint")?.textContent ?? "";
    return {
      position: {
        x: Number(document.body.dataset.playerX),
        y: Number(document.body.dataset.playerY)
      },
      hint,
      hintReady: hintText.length > 0 && hint.includes(hintText)
    };
  }, { hintText });
}

function movementKey(axis: "x" | "y", current: number, target: number): MovementKey {
  if (axis === "x") return current < target ? "d" : "a";
  return current < target ? "s" : "w";
}

function reachedOrCrossedTarget(
  key: MovementKey,
  current: number,
  target: number,
  tolerance = TARGET_TOLERANCE
): boolean {
  if (!Number.isFinite(current)) return false;
  if (Math.abs(current - target) <= tolerance) return true;
  return key === "d" || key === "s" ? current >= target : current <= target;
}

async function pulseKeys(
  page: Page,
  keys: MovementKey[],
  pulseMs = STEERING_PULSE_MS,
  knownStart?: PlayerPosition
): Promise<{ start: PlayerPosition; end: PlayerPosition }> {
  const uniqueKeys = [...new Set(keys)];
  const start = knownStart ?? await playerPosition(page);
  for (const key of uniqueKeys) await page.keyboard.down(key);
  try {
    await page.waitForTimeout(pulseMs);
  } finally {
    if (!page.isClosed()) {
      for (const key of [...uniqueKeys].reverse()) await page.keyboard.up(key);
    }
  }
  return { start, end: await playerPositionAfterBrowserFrame(page) };
}

async function recordPulse(
  page: Page,
  keys: MovementKey[],
  targetX: number,
  targetY: number,
  start: PlayerPosition,
  end: PlayerPosition
): Promise<void> {
  if (keys.includes("a") || keys.includes("d")) {
    await recordAxisTrace(page, { axis: "x", target: targetX, reached: start, released: end });
  }
  if (keys.includes("w") || keys.includes("s")) {
    await recordAxisTrace(page, { axis: "y", target: targetY, reached: start, released: end });
  }
}

function axisPulseDuration(gap: number, pulseMs: number): number {
  if (gap < 24) return 25;
  if (gap < 60) return Math.min(pulseMs, 45);
  return pulseMs;
}

export async function moveAxisTo(
  page: Page,
  axis: "x" | "y",
  target: number,
  tolerance = 8,
  timeout = 10_000,
  pulseMs = STEERING_PULSE_MS
): Promise<void> {
  const deadline = Date.now() + timeout;
  let current = await playerPosition(page);
  const initialValue = current[axis];
  if (!Number.isFinite(initialValue)) {
    throw new Error(`player position is invalid before ${axis}=${target}; start=${JSON.stringify(current)}`);
  }
  if (Math.abs(initialValue - target) <= tolerance) return;

  const key = movementKey(axis, initialValue, target);
  let stagnantPulses = 0;
  let pulses = 0;
  let lastTrace: AxisTrace | null = null;
  while (Date.now() < deadline && pulses < 96) {
    const currentValue = current[axis];
    if (!Number.isFinite(currentValue)) break;
    const gap = Math.abs(target - currentValue);
    if (reachedOrCrossedTarget(key, currentValue, target, tolerance)) return;

    const duration = axisPulseDuration(gap, pulseMs);
    const { start, end } = await pulseKeys(page, [key], duration, current);
    lastTrace = { axis, target, reached: start, released: end };
    pulses += 1;
    const endValue = end[axis];
    if (!Number.isFinite(endValue)) break;
    if (reachedOrCrossedTarget(key, endValue, target, tolerance)) {
      await recordAxisTrace(page, lastTrace);
      return;
    }

    const progress = Math.abs(endValue - start[axis]);
    stagnantPulses = progress < 1 ? stagnantPulses + 1 : 0;
    if (stagnantPulses >= 6) break;

    current = end;
  }

  if (lastTrace) await recordAxisTrace(page, lastTrace);
  await releaseMovementKeys(page);
  const end = await playerPosition(page);
  throw new Error(
    `player did not reach or cross ${axis}=${target}; last=${JSON.stringify(end)} `
      + `distance=${Math.round(Math.abs(end[axis] - target))} pulses=${pulses}`
  );
}

async function holdAxisUntilTarget(
  page: Page,
  axis: "x" | "y",
  target: number,
  tolerance: number,
  timeout: number
): Promise<PlayerPosition> {
  const start = await playerPosition(page);
  const startValue = start[axis];
  if (!Number.isFinite(startValue)) {
    throw new Error(`player position is invalid before held ${axis}=${target}; start=${JSON.stringify(start)}`);
  }
  if (Math.abs(startValue - target) <= tolerance) return start;

  const key = movementKey(axis, startValue, target);
  let waitError: unknown = null;
  await page.keyboard.down(key);
  try {
    await page.waitForFunction(
      ({ axis, target, key, tolerance }) => {
        const value = Number(axis === "x" ? document.body.dataset.playerX : document.body.dataset.playerY);
        if (!Number.isFinite(value)) return false;
        if (Math.abs(value - target) <= tolerance) return true;
        return key === "d" || key === "s" ? value >= target : value <= target;
      },
      { axis, target, key, tolerance },
      { timeout }
    );
  } catch (error) {
    waitError = error;
  } finally {
    if (!page.isClosed()) await page.keyboard.up(key);
  }

  const end = await playerPositionAfterBrowserFrame(page);
  await recordAxisTrace(page, { axis, target, reached: start, released: end });
  if (reachedOrCrossedTarget(key, end[axis], target, tolerance)) return end;

  const reason = waitError instanceof Error ? ` wait=${JSON.stringify(waitError.message)}` : "";
  throw new Error(
    `held movement ${key} did not reach or cross ${axis}=${target}; `
      + `last=${JSON.stringify(end)} distance=${Math.round(Math.abs(end[axis] - target))}${reason}`
  );
}

async function moveAxisIntoBand(
  page: Page,
  axis: "x" | "y",
  min: number,
  max: number,
  deadline: number
): Promise<PlayerPosition> {
  let current = await playerPosition(page);
  if (!Number.isFinite(current[axis])) {
    throw new Error(`player position is invalid before ${axis} band [${min}, ${max}]; start=${JSON.stringify(current)}`);
  }

  const initialBoundary = current[axis] < min ? min : max;
  if (Math.abs(initialBoundary - current[axis]) > 60) {
    current = await holdAxisUntilTarget(
      page,
      axis,
      initialBoundary,
      4,
      remainingRouteTime(deadline)
    );
    if (current[axis] >= min && current[axis] <= max) return current;
  }

  let stagnantPulses = 0;
  let pulses = 0;
  const traceTarget = Math.round((min + max) / 2);
  while (Date.now() < deadline && pulses < 64) {
    const value = current[axis];
    if (value >= min && value <= max) return current;

    const boundary = value < min ? min : max;
    const key = movementKey(axis, value, boundary);
    const gap = Math.abs(boundary - value);
    const duration = axisPulseDuration(gap, STEERING_PULSE_MS);
    const { start, end } = await pulseKeys(page, [key], duration, current);
    await recordAxisTrace(page, { axis, target: traceTarget, reached: start, released: end });
    pulses += 1;

    const endValue = end[axis];
    if (!Number.isFinite(endValue)) break;
    if (endValue >= min && endValue <= max) return end;

    const progress = Math.abs(endValue - start[axis]);
    stagnantPulses = progress < 1 ? stagnantPulses + 1 : 0;
    if (stagnantPulses >= 6) break;
    current = end;
  }

  await releaseMovementKeys(page);
  const end = await playerPosition(page);
  throw new Error(
    `player did not settle inside ${axis} band [${min}, ${max}]; `
      + `last=${JSON.stringify(end)} pulses=${pulses}`
  );
}

async function movePastVillageWell(page: Page, deadline: number): Promise<void> {
  let start = await playerPosition(page);
  if (!Number.isFinite(start.x) || !Number.isFinite(start.y)) {
    throw new Error(`physical route has invalid start before village well; start=${JSON.stringify(start)}`);
  }
  if (start.x >= VILLAGE_WELL_CLEAR_X) return;

  if (start.y < VILLAGE_LOWER_LANE_Y - TARGET_TOLERANCE) {
    await moveAxisTo(
      page,
      "y",
      VILLAGE_LOWER_LANE_Y,
      10,
      remainingRouteTime(deadline),
      STEERING_PULSE_MS
    );
    start = await playerPosition(page);
  }

  const end = await holdAxisUntilTarget(
    page,
    "x",
    VILLAGE_WELL_CLEAR_X,
    10,
    remainingRouteTime(deadline)
  );
  if (end.x >= VILLAGE_WELL_CLEAR_X - 10) return;

  throw new Error(`physical route did not clear village well; last=${JSON.stringify(end)}`);
}

function remainingRouteTime(deadline: number): number {
  return Math.max(1_000, deadline - Date.now());
}

function interactionAxisTarget(current: number, target: number): number {
  if (current < target - INTERACTION_AXIS_MARGIN) return target - INTERACTION_AXIS_MARGIN;
  if (current > target + INTERACTION_AXIS_MARGIN) return target + INTERACTION_AXIS_MARGIN;
  return current;
}

async function moveInteractionAxis(
  page: Page,
  axis: "x" | "y",
  target: number,
  hintText: string,
  deadline: number,
  deepenToCenter = false
): Promise<boolean> {
  const snapshot = await interactionSnapshot(page, hintText);
  if (snapshot.hintReady) return true;
  const current = snapshot.position[axis];
  if (!Number.isFinite(current)) return false;

  const key = Math.abs(current - target) > TARGET_TOLERANCE
    ? movementKey(axis, current, target)
    : null;
  const approachTarget = interactionAxisTarget(current, target);
  if (Math.abs(approachTarget - current) > TARGET_TOLERANCE) {
    await moveAxisTo(page, axis, approachTarget, 10, remainingRouteTime(deadline), STEERING_PULSE_MS);
  }
  await waitForBrowserFrame(page);
  let after = await interactionSnapshot(page, hintText);
  if (after.hintReady) return true;
  if (!deepenToCenter || !key) return false;

  const afterValue = after.position[axis];
  if (!Number.isFinite(afterValue) || reachedOrCrossedTarget(key, afterValue, target)) return false;
  await moveAxisTo(page, axis, target, 8, remainingRouteTime(deadline), STEERING_PULSE_MS);
  await waitForBrowserFrame(page);
  after = await interactionSnapshot(page, hintText);
  return after.hintReady;
}

async function steerInteractionToHint(
  page: Page,
  targetX: number,
  targetY: number,
  hintText: string,
  deadline: number
): Promise<void> {
  let stagnantPulses = 0;
  let pulses = 0;
  try {
    while (Date.now() < deadline && pulses < 48) {
      const snapshot = await interactionSnapshot(page, hintText);
      if (snapshot.hintReady) return;
      if (!Number.isFinite(snapshot.position.x) || !Number.isFinite(snapshot.position.y)) break;

      const dx = targetX - snapshot.position.x;
      const dy = targetY - snapshot.position.y;
      const keys: MovementKey[] = [];
      if (Math.abs(dx) > INTERACTION_AXIS_MARGIN) {
        keys.push(movementKey("x", snapshot.position.x, targetX));
      }
      if (Math.abs(dy) > INTERACTION_AXIS_MARGIN) {
        keys.push(movementKey("y", snapshot.position.y, targetY));
      }

      if (keys.length === 0) {
        if (Math.abs(dx) > TARGET_TOLERANCE && Math.abs(dx) >= Math.abs(dy)) {
          keys.push(movementKey("x", snapshot.position.x, targetX));
        } else if (Math.abs(dy) > TARGET_TOLERANCE) {
          keys.push(movementKey("y", snapshot.position.y, targetY));
        } else {
          await waitForBrowserFrame(page);
          if ((await interactionSnapshot(page, hintText)).hintReady) return;
          break;
        }
      }

      const gap = Math.max(Math.abs(dx), Math.abs(dy));
      const duration = axisPulseDuration(gap, STEERING_PULSE_MS);
      const { start, end } = await pulseKeys(page, keys, duration, snapshot.position);
      await recordPulse(page, keys, targetX, targetY, start, end);
      pulses += 1;

      const progress = Math.hypot(end.x - start.x, end.y - start.y);
      stagnantPulses = progress < 1 ? stagnantPulses + 1 : 0;
      if (stagnantPulses >= 6) break;
    }
  } finally {
    await releaseMovementKeys(page);
  }

  const snapshot = await interactionSnapshot(page, hintText);
  if (snapshot.hintReady) return;
  throw new Error(
    `target-aware steering did not reach ${JSON.stringify(hintText)}; `
      + `end=${JSON.stringify(snapshot.position)} hint=${JSON.stringify(snapshot.hint)} pulses=${pulses}`
  );
}

async function steerTavernApproachToHint(
  page: Page,
  targetX: number,
  targetY: number,
  hintText: string,
  deadline: number
): Promise<void> {
  const corridorY = VILLAGE_LOWER_LANE_Y;
  try {
    let snapshot = await interactionSnapshot(page, hintText);
    if (snapshot.hintReady) return;
    if (!Number.isFinite(snapshot.position.x) || !Number.isFinite(snapshot.position.y)) {
      throw new Error(`tavern approach has invalid start; start=${JSON.stringify(snapshot.position)}`);
    }

    if (Math.abs(snapshot.position.y - corridorY) > TARGET_TOLERANCE) {
      await moveAxisTo(page, "y", corridorY, 10, remainingRouteTime(deadline));
    }
    snapshot = await interactionSnapshot(page, hintText);
    if (snapshot.hintReady) return;

    await moveAxisIntoBand(
      page,
      "x",
      targetX - TAVERN_SAFE_X_MARGIN,
      targetX + TAVERN_SAFE_X_MARGIN,
      deadline
    );
    snapshot = await interactionSnapshot(page, hintText);
    if (snapshot.hintReady) return;

    await moveAxisIntoBand(page, "y", TAVERN_SAFE_Y_MIN, TAVERN_SAFE_Y_MAX, deadline);
    await waitForBrowserFrame(page);
    snapshot = await interactionSnapshot(page, hintText);
    if (snapshot.hintReady) return;

    await moveAxisIntoBand(
      page,
      "x",
      targetX - TAVERN_SAFE_X_MARGIN,
      targetX + TAVERN_SAFE_X_MARGIN,
      deadline
    );
    await waitForBrowserFrame(page);
    snapshot = await interactionSnapshot(page, hintText);
    if (snapshot.hintReady) return;

    await steerInteractionToHint(page, targetX, targetY, hintText, deadline);
  } finally {
    await releaseMovementKeys(page);
  }

  const snapshot = await interactionSnapshot(page, hintText);
  if (snapshot.hintReady) return;
  const diagnostics = await page.evaluate(() => document.body.dataset.movementTrace ?? null);
  throw new Error(
    `coordinate-steered tavern approach did not reach ${JSON.stringify(hintText)}; `
      + `end=${JSON.stringify(snapshot.position)} hint=${JSON.stringify(snapshot.hint)} `
      + `movementTrace=${JSON.stringify(diagnostics)}`
  );
}

async function moveToTavernInteraction(
  page: Page,
  targetX: number,
  targetY: number,
  hintText: string,
  deadline: number
): Promise<void> {
  const start = await playerPosition(page);
  if (start.x < VILLAGE_WELL_CLEAR_X) await movePastVillageWell(page, deadline);
  if ((await interactionSnapshot(page, hintText)).hintReady) return;

  await steerTavernApproachToHint(page, targetX, targetY, hintText, deadline);
}

export async function moveTowardInteraction(
  page: Page,
  targetX: number,
  targetY: number,
  hintText: string,
  timeout = 12_000
): Promise<void> {
  await installNavigationDiagnostics(page);
  await releaseMovementKeys(page);
  const deadline = Date.now() + timeout;

  if (targetX >= 700 && targetY <= 360 && hintText.includes("войти в таверну")) {
    await moveToTavernInteraction(page, targetX, targetY, hintText, deadline);
    return;
  }

  const steeringStart = await interactionSnapshot(page, hintText);
  if (steeringStart.hintReady) return;
  const startX = steeringStart.position.x;
  const startY = steeringStart.position.y;
  if (!Number.isFinite(startX) || !Number.isFinite(startY)) {
    throw new Error(`player position is invalid before interaction steering; start=${JSON.stringify(steeringStart.position)}`);
  }

  if (await moveInteractionAxis(page, "x", targetX, hintText, deadline)) return;
  if (await moveInteractionAxis(page, "y", targetY, hintText, deadline, true)) return;
  if (await moveInteractionAxis(page, "x", targetX, hintText, deadline, true)) return;

  const snapshot = await interactionSnapshot(page, hintText);
  if (snapshot.hintReady) return;
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
    `player did not reach interaction ${JSON.stringify(hintText)} near (${targetX}, ${targetY}); `
      + `last=${JSON.stringify(snapshot.position)} distance=${Math.round(gap)} `
      + `hint=${JSON.stringify(snapshot.hint)} diagnostics=${JSON.stringify(diagnostics)}`
  );
}

async function moveWithConcurrentKeysUntilHint(
  page: Page,
  keys: MovementKey[],
  hintText: string,
  timeout: number,
  pulseMs = STEERING_PULSE_MS
): Promise<void> {
  await installNavigationDiagnostics(page);
  await releaseMovementKeys(page);

  if (keys.length === 1) {
    const key = keys[0];
    let waitError: unknown = null;
    await page.keyboard.down(key);
    try {
      await page.waitForFunction(
        ({ hintText }) => (document.getElementById("interaction-hint")?.textContent ?? "").includes(hintText),
        { hintText },
        { timeout }
      );
    } catch (error) {
      waitError = error;
    } finally {
      if (!page.isClosed()) await page.keyboard.up(key);
    }
    await waitForBrowserFrame(page);
    const snapshot = await interactionSnapshot(page, hintText);
    if (snapshot.hintReady) return;
    const reason = waitError instanceof Error ? ` wait=${JSON.stringify(waitError.message)}` : "";
    throw new Error(
      `movement ${key} did not reach ${JSON.stringify(hintText)}; `
        + `end=${JSON.stringify(snapshot.position)} hint=${JSON.stringify(snapshot.hint)}${reason}`
    );
  }

  const deadline = Date.now() + timeout;
  let stagnantPulses = 0;
  try {
    while (Date.now() < deadline) {
      const snapshot = await interactionSnapshot(page, hintText);
      if (snapshot.hintReady) return;
      const { start, end } = await pulseKeys(page, keys, pulseMs);
      const progress = Math.hypot(end.x - start.x, end.y - start.y);
      stagnantPulses = progress < 1 ? stagnantPulses + 1 : 0;
      if (stagnantPulses >= 6) break;
    }
  } finally {
    await releaseMovementKeys(page);
  }

  const snapshot = await interactionSnapshot(page, hintText);
  if (!snapshot.hintReady) {
    throw new Error(
      `movement ${keys.join("+")} did not reach ${JSON.stringify(hintText)}; `
        + `end=${JSON.stringify(snapshot.position)} hint=${JSON.stringify(snapshot.hint)}`
    );
  }
}

export async function enterTavernSpatially(page: Page): Promise<void> {
  const hint = page.locator("#interaction-hint");
  await installNavigationDiagnostics(page);
  await releaseMovementKeys(page);
  const routeDeadline = Date.now() + 20_000;

  await moveTowardInteraction(page, 825, 330, "войти в таверну", remainingRouteTime(routeDeadline));
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