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
  await waitForBrowserFrame(page);
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
  pulseMs = STEERING_PULSE_MS
): Promise<{ start: PlayerPosition; end: PlayerPosition }> {
  const uniqueKeys = [...new Set(keys)];
  const start = await playerPosition(page);
  for (const key of uniqueKeys) await page.keyboard.down(key);
  try {
    // Keep real keys down across the awaited interval. If the external controller
    // is delayed, the independently rendering browser can continue physical movement.
    // When control resumes we release, observe the real position and correct course.
    await page.waitForTimeout(pulseMs);
  } finally {
    if (!page.isClosed()) {
      for (const key of [...uniqueKeys].reverse()) await page.keyboard.up(key);
    }
  }
  await waitForBrowserFrame(page);
  return { start, end: await playerPosition(page) };
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

export async function moveAxisTo(
  page: Page,
  axis: "x" | "y",
  target: number,
  tolerance = 8,
  timeout = 10_000,
  pulseMs = STEERING_PULSE_MS
): Promise<void> {
  await installNavigationDiagnostics(page);
  await releaseMovementKeys(page);
  const deadline = Date.now() + timeout;
  const initial = await playerPosition(page);
  const initialValue = initial[axis];
  if (!Number.isFinite(initialValue)) {
    throw new Error(`player position is invalid before ${axis}=${target}; start=${JSON.stringify(initial)}`);
  }
  if (Math.abs(initialValue - target) <= tolerance) return;

  // Pick one physical direction for this axis and keep it for the whole approach.
  // A delayed key release may carry the avatar past the exact coordinate, so crossing
  // the target is success. Reversing after a crossing creates the oscillation seen in CI.
  const key = movementKey(axis, initialValue, target);
  let stagnantPulses = 0;

  try {
    while (Date.now() < deadline) {
      const before = await playerPosition(page);
      const value = before[axis];
      if (reachedOrCrossedTarget(key, value, target, tolerance)) return;
      if (!Number.isFinite(value)) break;

      const { start, end } = await pulseKeys(page, [key], pulseMs);
      await recordAxisTrace(page, { axis, target, reached: start, released: end });
      if (reachedOrCrossedTarget(key, end[axis], target, tolerance)) return;

      const progress = Math.abs(end[axis] - start[axis]);
      stagnantPulses = progress < 1 ? stagnantPulses + 1 : 0;
      if (stagnantPulses >= 5) break;
    }
  } finally {
    await releaseMovementKeys(page);
  }

  throw new Error(`player did not reach ${axis}=${target}; last=${JSON.stringify(await playerPosition(page))}`);
}

async function movePastVillageWell(page: Page, deadline: number): Promise<void> {
  let stagnantPulses = 0;
  while (Date.now() < deadline) {
    const before = await playerPosition(page);
    if (!Number.isFinite(before.x) || !Number.isFinite(before.y)) break;
    if (before.x >= VILLAGE_WELL_CLEAR_X) return;

    const keys: MovementKey[] = ["d"];
    // The well occupies x=435..540 and y=330..420. Use the real S key until the
    // avatar is on the collision-free lower lane, then keep moving right. Longer
    // corridor pulses reduce Playwright round-trips under CPU throttling without
    // changing the real key, collision or gameplay-speed semantics.
    if (before.y < VILLAGE_LOWER_LANE_Y) keys.push("s");
    const { start, end } = await pulseKeys(page, keys, CORRIDOR_PULSE_MS);
    await recordPulse(page, keys, VILLAGE_WELL_CLEAR_X, VILLAGE_LOWER_LANE_Y, start, end);
    const progress = Math.hypot(end.x - start.x, end.y - start.y);
    stagnantPulses = progress < 1 ? stagnantPulses + 1 : 0;
    if (stagnantPulses >= 6) break;
  }

  const last = await playerPosition(page);
  if (last.x < VILLAGE_WELL_CLEAR_X) {
    throw new Error(`physical route did not clear village well; last=${JSON.stringify(last)}`);
  }
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

  // Interaction targets are centers, not exact coordinates. First stop near the
  // interaction edge. This limits travel under delayed keyup and is enough for most
  // targets without requiring pixel-perfect steering.
  const approachTarget = interactionAxisTarget(current, target);
  if (Math.abs(approachTarget - current) > TARGET_TOLERANCE) {
    await moveAxisTo(
      page,
      axis,
      approachTarget,
      10,
      remainingRouteTime(deadline),
      STEERING_PULSE_MS
    );
  }
  await waitForBrowserFrame(page);
  let after = await interactionSnapshot(page, hintText);
  if (after.hintReady) return true;
  if (!deepenToCenter || !key) return false;

  // Some requested interactions overlap higher-priority hotspots. Mira and nearby
  // firewood are the canonical example: reaching the outer NPC radius can still show
  // the wood action. Continue in the same physical direction toward the NPC center,
  // but never reverse after already crossing it. The scene's interaction grace then
  // preserves the requested hint long enough for the controller to observe it.
  const afterValue = after.position[axis];
  if (!Number.isFinite(afterValue) || reachedOrCrossedTarget(key, afterValue, target)) return false;
  await moveAxisTo(
    page,
    axis,
    target,
    8,
    remainingRouteTime(deadline),
    STEERING_PULSE_MS
  );
  await waitForBrowserFrame(page);
  after = await interactionSnapshot(page, hintText);
  return after.hintReady;
}

async function moveToTavernInteraction(
  page: Page,
  targetX: number,
  hintText: string,
  deadline: number
): Promise<void> {
  const start = await playerPosition(page);
  if (start.x < VILLAGE_WELL_CLEAR_X) await movePastVillageWell(page, deadline);
  if ((await interactionSnapshot(page, hintText)).hintReady) return;

  // Stay on the collision-free lower lane while crossing the village and the full
  // width of the tavern facade. Only then move vertically toward the door. This
  // makes controller delay harmless: horizontal overshoot happens in open space,
  // while the tavern wall itself safely bounds the later upward movement.
  const lowerApproachX = targetX - 20;
  await moveAxisTo(
    page,
    "x",
    lowerApproachX,
    18,
    remainingRouteTime(deadline),
    CORRIDOR_PULSE_MS
  );
  if ((await interactionSnapshot(page, hintText)).hintReady) return;

  await moveWithConcurrentKeysUntilHint(
    page,
    ["w"],
    hintText,
    remainingRouteTime(deadline),
    CORRIDOR_PULSE_MS
  );
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

  // The tavern sits above a long collision-free lower corridor. A sequential
  // corridor route is more robust than diagonal steering because a delayed keyup
  // can no longer spend the route budget pushing one axis into a building edge.
  if (targetX >= 700 && targetY <= 360 && hintText.includes("войти в таверну")) {
    await moveToTavernInteraction(page, targetX, hintText, deadline);
    return;
  }

  const steeringStart = await interactionSnapshot(page, hintText);
  if (steeringStart.hintReady) return;
  const startX = steeringStart.position.x;
  const startY = steeringStart.position.y;
  if (!Number.isFinite(startX) || !Number.isFinite(startY)) {
    throw new Error(`player position is invalid before interaction steering; start=${JSON.stringify(steeringStart.position)}`);
  }

  // Keep only one physical movement key active at a time. In a throttled browser,
  // Playwright key commands can be delayed asymmetrically; a nominal diagonal pulse
  // can therefore move one axis by ~100px before the other key is released. Sequential
  // axes preserve real keyboard semantics and let the scene's interaction grace catch
  // the actual spatial pass through the target radius.
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

  // A single open-axis leg should keep one real movement key held while the browser
  // itself watches the requested interaction surface. This avoids spending the
  // remaining route budget on repeated Playwright key down/up round-trips under CPU
  // throttling, while preserving the exact WASD event, collision and gameplay speed.
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

  await moveTowardInteraction(
    page,
    825,
    330,
    "войти в таверну",
    remainingRouteTime(routeDeadline)
  );
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