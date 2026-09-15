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
};

type AxisDriveResult = {
  reachedTargetBand: boolean;
  hintReady: boolean;
  moved: boolean;
};

type AxisMonitorResult = {
  position: PlayerPosition;
  hint: string;
  hintReady: boolean;
  reachedTargetBand: boolean;
  stalled: boolean;
  timedOut: boolean;
};

type VectorDriveResult = {
  hintReady: boolean;
  moved: boolean;
  reachedAxis: boolean;
};

type VectorMonitorResult = {
  position: PlayerPosition;
  hint: string;
  hintReady: boolean;
  reachedAxis: boolean;
  stalled: boolean;
  timedOut: boolean;
};

const MOVEMENT_KEYS = ["w", "a", "s", "d"] as const;

export async function playerPosition(page: Page): Promise<PlayerPosition> {
  return page.evaluate(() => ({
    x: Number(document.body.dataset.playerX),
    y: Number(document.body.dataset.playerY)
  }));
}

async function waitForBrowserFrame(page: Page): Promise<void> {
  if (page.isClosed()) return;
  await page.evaluate(() => new Promise<void>((resolve) => {
    requestAnimationFrame(() => resolve());
  }));
}

export async function releaseMovementKeys(page: Page): Promise<void> {
  if (page.isClosed()) return;
  // Playwright Keyboard keeps state per page, so release the physical keys in order
  // and let one real browser frame observe the released state before steering again.
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
  let heldKey: MovementKey | null = null;
  let reached: PlayerPosition | null = null;
  await releaseMovementKeys(page);
  const started = Date.now();
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
    if (heldKey && !page.isClosed()) await page.keyboard.up(heldKey);
    await releaseMovementKeys(page);
  }

  const released = await playerPosition(page);
  if (reached) {
    await recordAxisTrace(page, { axis, target, reached, released });
    return;
  }
  throw new Error(`player did not reach ${axis}=${target}; last=${JSON.stringify(released)}`);
}

async function monitorHeldAxis(
  page: Page,
  axis: "x" | "y",
  target: number,
  hintText: string,
  key: MovementKey,
  timeoutMs: number,
  targetBand: number
): Promise<AxisMonitorResult> {
  return page.evaluate(async ({ axis, target, hintText, key, timeoutMs, targetBand }) => {
    const readSnapshot = () => {
      const position = {
        x: Number(document.body.dataset.playerX),
        y: Number(document.body.dataset.playerY)
      };
      const hint = document.getElementById("interaction-hint")?.textContent ?? "";
      return { position, hint };
    };

    const initial = readSnapshot();
    let lastValue = initial.position[axis];
    let lastProgressAt = performance.now();
    const positive = key === "d" || key === "s";
    const started = performance.now();

    return await new Promise<AxisMonitorResult>((resolve) => {
      const finish = (
        snapshot: InteractionSnapshot,
        reachedTargetBand: boolean,
        stalled: boolean,
        timedOut: boolean
      ): void => {
        resolve({
          position: snapshot.position,
          hint: snapshot.hint,
          hintReady: hintText.length > 0 && snapshot.hint.includes(hintText),
          reachedTargetBand,
          stalled,
          timedOut
        });
      };

      const sample = (): void => {
        const snapshot = readSnapshot();
        if (hintText.length > 0 && snapshot.hint.includes(hintText)) {
          finish(snapshot, false, false, false);
          return;
        }

        const current = snapshot.position[axis];
        if (!Number.isFinite(current)) {
          finish(snapshot, false, true, false);
          return;
        }

        const crossed = positive ? current >= target : current <= target;
        if (crossed || Math.abs(current - target) <= targetBand) {
          finish(snapshot, true, false, false);
          return;
        }

        const now = performance.now();
        if (Number.isFinite(lastValue) && Math.abs(current - lastValue) >= 1) lastProgressAt = now;
        lastValue = current;

        // Phaser and this diagnostic sampler both run from requestAnimationFrame.
        // Use elapsed no-progress time rather than a frame count so a slow runner
        // cannot mistake several sampler frames for a physically blocked player.
        if (now - lastProgressAt >= 900) {
          finish(snapshot, false, true, false);
          return;
        }
        if (now - started >= Math.max(1, timeoutMs)) {
          finish(snapshot, false, false, true);
          return;
        }
        requestAnimationFrame(sample);
      };

      requestAnimationFrame(sample);
    });
  }, { axis, target, hintText, key, timeoutMs, targetBand });
}

async function settledInteractionSnapshot(
  page: Page,
  hintText: string
): Promise<InteractionSnapshot & { hintReady: boolean }> {
  return page.evaluate(async ({ hintText }) => {
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    const position = {
      x: Number(document.body.dataset.playerX),
      y: Number(document.body.dataset.playerY)
    };
    const hint = document.getElementById("interaction-hint")?.textContent ?? "";
    return {
      position,
      hint,
      hintReady: hintText.length > 0 && hint.includes(hintText)
    };
  }, { hintText });
}

async function moveAxisOneWayTo(
  page: Page,
  axis: "x" | "y",
  target: number,
  timeout = 8_000
): Promise<void> {
  await installNavigationDiagnostics(page);
  const start = await playerPosition(page);
  const value = start[axis];
  if (!Number.isFinite(value) || value === target) return;

  const key: MovementKey = axis === "x"
    ? (value < target ? "d" : "a")
    : (value < target ? "s" : "w");
  const targetBand = 12;
  let observed: AxisMonitorResult | null = null;

  await releaseMovementKeys(page);
  await page.keyboard.down(key);
  try {
    observed = await monitorHeldAxis(page, axis, target, "", key, timeout, targetBand);
  } finally {
    if (!page.isClosed()) await page.keyboard.up(key);
  }

  const released = await settledInteractionSnapshot(page, "");
  const current = released.position[axis];
  const reached = Number.isFinite(current)
    && (crossedTarget(key, current, target) || Math.abs(current - target) <= targetBand);
  await recordAxisTrace(page, {
    axis,
    target,
    reached: observed?.position ?? released.position,
    released: released.position
  });
  if (!reached) {
    throw new Error(
      `one-way ${key} movement did not reach ${axis}=${target}; `
        + `start=${JSON.stringify(start)} end=${JSON.stringify(released.position)}`
    );
  }
}

async function interactionSnapshot(
  page: Page,
  hintText: string
): Promise<InteractionSnapshot & { hintReady: boolean }> {
  return page.evaluate(({ hintText }) => {
    const position = {
      x: Number(document.body.dataset.playerX),
      y: Number(document.body.dataset.playerY)
    };
    const hint = document.getElementById("interaction-hint")?.textContent ?? "";
    return {
      position,
      hint,
      hintReady: hintText.length > 0 && hint.includes(hintText)
    };
  }, { hintText });
}

function axisKey(axis: "x" | "y", current: number, target: number): MovementKey {
  return axis === "x"
    ? (current < target ? "d" : "a")
    : (current < target ? "s" : "w");
}

function crossedTarget(key: MovementKey, current: number, target: number): boolean {
  return key === "d" || key === "s" ? current >= target : current <= target;
}

async function driveSingleAxisUntilHintOrTarget(
  page: Page,
  axis: "x" | "y",
  target: number,
  hintText: string,
  deadline: number
): Promise<AxisDriveResult> {
  const start = await interactionSnapshot(page, hintText);
  if (start.hintReady) return { reachedTargetBand: false, hintReady: true, moved: false };

  const startValue = start.position[axis];
  if (!Number.isFinite(startValue)) {
    return { reachedTargetBand: false, hintReady: false, moved: false };
  }
  if (Math.abs(startValue - target) <= 4) {
    return { reachedTargetBand: true, hintReady: false, moved: false };
  }

  const key = axisKey(axis, startValue, target);
  const targetBand = 4;
  const remaining = Math.max(1, deadline - Date.now());
  let observed: AxisMonitorResult | null = null;

  await page.keyboard.down(key);
  try {
    observed = await monitorHeldAxis(page, axis, target, hintText, key, remaining, targetBand);
  } finally {
    if (!page.isClosed()) await page.keyboard.up(key);
  }

  const released = await settledInteractionSnapshot(page, hintText);
  const releasedValue = released.position[axis];
  const reachedAfterRelease = Number.isFinite(releasedValue)
    && (crossedTarget(key, releasedValue, target) || Math.abs(releasedValue - target) <= targetBand);
  await recordAxisTrace(page, {
    axis,
    target,
    reached: observed?.position ?? released.position,
    released: released.position
  });
  return {
    reachedTargetBand: reachedAfterRelease,
    hintReady: released.hintReady,
    moved: Math.abs(releasedValue - startValue) >= 1
  };
}

async function monitorHeldVector(
  page: Page,
  targetX: number,
  targetY: number,
  hintText: string,
  xKey: MovementKey | null,
  yKey: MovementKey | null,
  timeoutMs: number,
  targetBand: number
): Promise<VectorMonitorResult> {
  return page.evaluate(async ({ targetX, targetY, hintText, xKey, yKey, timeoutMs, targetBand }) => {
    const readSnapshot = () => {
      const position = {
        x: Number(document.body.dataset.playerX),
        y: Number(document.body.dataset.playerY)
      };
      const hint = document.getElementById("interaction-hint")?.textContent ?? "";
      return { position, hint };
    };
    const crossed = (key: MovementKey, current: number, target: number): boolean =>
      key === "d" || key === "s" ? current >= target : current <= target;

    const initial = readSnapshot();
    let last = initial.position;
    let lastProgressAt = performance.now();
    const started = performance.now();

    return await new Promise<VectorMonitorResult>((resolve) => {
      const finish = (
        snapshot: InteractionSnapshot,
        reachedAxis: boolean,
        stalled: boolean,
        timedOut: boolean
      ): void => resolve({
        position: snapshot.position,
        hint: snapshot.hint,
        hintReady: hintText.length > 0 && snapshot.hint.includes(hintText),
        reachedAxis,
        stalled,
        timedOut
      });

      const sample = (): void => {
        const snapshot = readSnapshot();
        if (hintText.length > 0 && snapshot.hint.includes(hintText)) {
          finish(snapshot, false, false, false);
          return;
        }
        const { x, y } = snapshot.position;
        if (!Number.isFinite(x) || !Number.isFinite(y)) {
          finish(snapshot, false, true, false);
          return;
        }

        const reachedX = xKey !== null && (crossed(xKey, x, targetX) || Math.abs(x - targetX) <= targetBand);
        const reachedY = yKey !== null && (crossed(yKey, y, targetY) || Math.abs(y - targetY) <= targetBand);
        if (reachedX || reachedY) {
          finish(snapshot, true, false, false);
          return;
        }

        const now = performance.now();
        if (Math.hypot(x - last.x, y - last.y) >= 1) lastProgressAt = now;
        last = snapshot.position;
        if (now - lastProgressAt >= 900) {
          finish(snapshot, false, true, false);
          return;
        }
        if (now - started >= Math.max(1, timeoutMs)) {
          finish(snapshot, false, false, true);
          return;
        }
        requestAnimationFrame(sample);
      };
      requestAnimationFrame(sample);
    });
  }, { targetX, targetY, hintText, xKey, yKey, timeoutMs, targetBand });
}

async function driveConcurrentSegment(
  page: Page,
  targetX: number,
  targetY: number,
  hintText: string,
  deadline: number
): Promise<VectorDriveResult> {
  const start = await interactionSnapshot(page, hintText);
  if (start.hintReady) return { hintReady: true, moved: false, reachedAxis: false };

  const dx = targetX - start.position.x;
  const dy = targetY - start.position.y;
  const targetBand = 4;
  const xKey = Number.isFinite(dx) && Math.abs(dx) > targetBand
    ? axisKey("x", start.position.x, targetX)
    : null;
  const yKey = Number.isFinite(dy) && Math.abs(dy) > targetBand
    ? axisKey("y", start.position.y, targetY)
    : null;
  const keys = [xKey, yKey].filter((key): key is MovementKey => key !== null);
  if (keys.length === 0) return { hintReady: false, moved: false, reachedAxis: true };

  const remaining = Math.max(1, deadline - Date.now());
  for (const key of keys) await page.keyboard.down(key);
  let observed: VectorMonitorResult | null = null;
  try {
    observed = await monitorHeldVector(
      page,
      targetX,
      targetY,
      hintText,
      xKey,
      yKey,
      remaining,
      targetBand
    );
  } finally {
    if (!page.isClosed()) {
      for (const key of keys) await page.keyboard.up(key);
    }
  }

  const released = await settledInteractionSnapshot(page, hintText);
  if (xKey) {
    await recordAxisTrace(page, {
      axis: "x",
      target: targetX,
      reached: observed?.position ?? released.position,
      released: released.position
    });
  }
  if (yKey) {
    await recordAxisTrace(page, {
      axis: "y",
      target: targetY,
      reached: observed?.position ?? released.position,
      released: released.position
    });
  }
  return {
    hintReady: released.hintReady,
    moved: Math.hypot(
      released.position.x - start.position.x,
      released.position.y - start.position.y
    ) >= 1,
    reachedAxis: Boolean(observed?.reachedAxis)
  };
}

export async function moveTowardInteraction(
  page: Page,
  targetX: number,
  targetY: number,
  hintText: string,
  timeout = 12_000
): Promise<void> {
  await installNavigationDiagnostics(page);
  let stalledRounds = 0;

  await releaseMovementKeys(page);
  const deadline = Date.now() + timeout;
  try {
    while (Date.now() < deadline) {
      let snapshot = await interactionSnapshot(page, hintText);
      if (snapshot.hintReady) {
        await releaseMovementKeys(page);
        snapshot = await interactionSnapshot(page, hintText);
        if (snapshot.hintReady) return;
      }

      const dx = targetX - snapshot.position.x;
      const dy = targetY - snapshot.position.y;
      if (!Number.isFinite(dx) || !Number.isFinite(dy)) break;
      if (Math.abs(dx) <= 4 && Math.abs(dy) <= 4) break;

      // Long lateral approaches in the village need to stay in the open lower lane
      // until they clear the workshop/well geometry. For ordinary interactions,
      // drive both physical axes together so a slow controller does not spend the
      // whole shared deadline completing only the first axis.
      const absX = Math.abs(dx);
      const absY = Math.abs(dy);
      let result: AxisDriveResult | VectorDriveResult;
      if (absX > 4 && absX >= Math.max(1, absY) * 3) {
        result = await driveSingleAxisUntilHintOrTarget(page, "x", targetX, hintText, deadline);
      } else if (absY > 4 && absY >= Math.max(1, absX) * 3) {
        result = await driveSingleAxisUntilHintOrTarget(page, "y", targetY, hintText, deadline);
      } else {
        result = await driveConcurrentSegment(page, targetX, targetY, hintText, deadline);
      }

      snapshot = await interactionSnapshot(page, hintText);
      if (result.hintReady || snapshot.hintReady) {
        await releaseMovementKeys(page);
        snapshot = await interactionSnapshot(page, hintText);
        if (snapshot.hintReady) return;
      }

      const reachedTarget = "reachedTargetBand" in result && result.reachedTargetBand;
      const reachedAxis = "reachedAxis" in result && result.reachedAxis;
      if (result.moved || reachedTarget || reachedAxis) {
        stalledRounds = 0;
      } else {
        stalledRounds += 1;
      }
      if (stalledRounds >= 3) break;
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
    if (!page.isClosed()) {
      for (const key of keys) await page.keyboard.up(key);
    }
    await releaseMovementKeys(page);
  }
}

export async function enterTavernSpatially(page: Page): Promise<void> {
  const hint = page.locator("#interaction-hint");
  // The tavern collision body occupies the upper lane. Align with the doorway while
  // still in the open plaza, then approach north through the real interaction band.
  await moveAxisOneWayTo(page, "x", 825, 20_000);
  await moveTowardInteraction(page, 825, 330, "войти в таверну", 20_000);
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
