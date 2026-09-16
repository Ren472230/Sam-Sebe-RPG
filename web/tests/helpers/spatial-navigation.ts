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
const TARGET_TOLERANCE = 7;

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
  timeout = 10_000
): Promise<void> {
  await installNavigationDiagnostics(page);
  await releaseMovementKeys(page);
  const deadline = Date.now() + timeout;
  let stagnantPulses = 0;

  try {
    while (Date.now() < deadline) {
      const before = await playerPosition(page);
      const value = before[axis];
      if (Number.isFinite(value) && Math.abs(value - target) <= tolerance) return;
      if (!Number.isFinite(value)) break;

      const key = movementKey(axis, value, target);
      const { start, end } = await pulseKeys(page, [key]);
      await recordAxisTrace(page, { axis, target, reached: start, released: end });
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
    // avatar is on the collision-free lower lane, then keep moving right.
    if (before.y < VILLAGE_LOWER_LANE_Y) keys.push("s");
    const { start, end } = await pulseKeys(page, keys);
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
  let stagnantPulses = 0;

  // A direct target-aware tavern approach can start on the workshop side of the
  // village well. Route that long crossing through the same lower physical lane
  // used by the canonical tavern helper before fine target steering begins.
  const initial = await playerPosition(page);
  if (
    targetX >= 700
    && targetY <= 360
    && initial.x < VILLAGE_WELL_CLEAR_X
  ) {
    await movePastVillageWell(page, deadline);
  }

  try {
    while (Date.now() < deadline) {
      const snapshot = await interactionSnapshot(page, hintText);
      if (snapshot.hintReady) return;
      const { x, y } = snapshot.position;
      if (!Number.isFinite(x) || !Number.isFinite(y)) break;

      const dx = targetX - x;
      const dy = targetY - y;
      const keys: MovementKey[] = [];
      if (Math.abs(dx) > TARGET_TOLERANCE) keys.push(movementKey("x", x, targetX));
      if (Math.abs(dy) > TARGET_TOLERANCE) keys.push(movementKey("y", y, targetY));

      if (keys.length === 0) {
        // The supplied coordinate is an approach point. Probe one physical step so
        // a nearby interaction radius can refresh before declaring failure.
        keys.push(y >= targetY ? "w" : "s");
      }

      const { start, end } = await pulseKeys(page, keys);
      await recordPulse(page, keys, targetX, targetY, start, end);

      const after = await interactionSnapshot(page, hintText);
      if (after.hintReady) return;

      const progress = Math.hypot(end.x - start.x, end.y - start.y);
      stagnantPulses = progress < 1 ? stagnantPulses + 1 : 0;
      if (stagnantPulses >= 6) break;
    }
  } finally {
    await releaseMovementKeys(page);
  }

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
  timeout: number
): Promise<void> {
  await installNavigationDiagnostics(page);
  await releaseMovementKeys(page);
  const deadline = Date.now() + timeout;
  let stagnantPulses = 0;

  try {
    while (Date.now() < deadline) {
      const snapshot = await interactionSnapshot(page, hintText);
      if (snapshot.hintReady) return;
      const { start, end } = await pulseKeys(page, keys);
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

  const start = await playerPosition(page);
  if (start.x < VILLAGE_WELL_CLEAR_X) await movePastVillageWell(page, routeDeadline);

  const remainingForLane = Math.max(1_000, routeDeadline - Date.now());
  await moveAxisTo(page, "x", 825, 12, Math.min(12_000, remainingForLane));
  const remainingForApproach = Math.max(1_000, routeDeadline - Date.now());
  await moveTowardInteraction(page, 825, 330, "войти в таверну", remainingForApproach);
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
