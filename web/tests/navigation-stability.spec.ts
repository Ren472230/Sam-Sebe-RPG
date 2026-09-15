import { expect, test, type Page } from "@playwright/test";

import {
  approachAndTalk,
  enterTavernSpatially,
  moveTowardInteraction,
  releaseMovementKeys
} from "./helpers/spatial-navigation";

async function useIsolatedPlayer(page: Page, externalId: string): Promise<void> {
  await page.route("**/api/session", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      await route.continue();
      return;
    }
    const payload = request.postDataJSON() as { external_id?: string; name?: string };
    await route.continue({
      postData: JSON.stringify({ ...payload, external_id: externalId })
    });
  });
}

async function placePlayerInTavern(page: Page, externalId: string): Promise<void> {
  const sessionResponse = await page.request.post("/api/session", {
    data: { external_id: externalId, name: "Ren" }
  });
  expect(sessionResponse.ok()).toBeTruthy();
  const session = await sessionResponse.json() as { player_id: string };

  for (const destination of ["village_square", "tavern_interior"] as const) {
    const actionResponse = await page.request.post("/api/action", {
      data: {
        player_id: session.player_id,
        action_type: "MOVE",
        target_id: null,
        recipient_id: null,
        destination_id: destination,
        modifiers: null,
        external_id: `${externalId}-${destination}`
      }
    });
    expect(actionResponse.ok()).toBeTruthy();
    const action = await actionResponse.json() as { success: boolean; summary: string };
    expect(action.success, action.summary).toBe(true);
  }
}

test("spatial tavern entry survives a slower browser", async ({ page, context }) => {
  test.setTimeout(45_000);
  await useIsolatedPlayer(page, "e2e-nav-slow-player");
  const cdp = await context.newCDPSession(page);

  try {
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
    await page.goto("/");
    await expect(page.locator("body")).toHaveAttribute("data-scene", "village");

    await enterTavernSpatially(page);
    await expect(page.locator("body")).toHaveAttribute("data-scene", "tavern", { timeout: 10_000 });
  } finally {
    await releaseMovementKeys(page);
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 }).catch(() => undefined);
  }
});

test("target-aware interaction recovers after the controller misses a crossing", async ({ page }) => {
  test.setTimeout(45_000);
  await useIsolatedPlayer(page, "e2e-nav-controller-stall-player");
  await page.goto("/");
  await expect(page.locator("body")).toHaveAttribute("data-scene", "village");

  const movement = moveTowardInteraction(page, 825, 330, "войти в таверну", 20_000);
  await page.waitForFunction(() => {
    const debugWindow = window as Window & { __navKeyTrace?: string[] };
    return (debugWindow.__navKeyTrace ?? []).some((entry) => entry.startsWith("down:"));
  });

  const blockedUntil = Date.now() + 700;
  while (Date.now() < blockedUntil) {
    // Deliberately block the Playwright controller while the browser keeps held movement keys active.
  }

  try {
    await movement;
    await expect(page.locator("#interaction-hint")).toContainText("войти в таверну");
  } finally {
    await releaseMovementKeys(page);
  }
});

test("controller stall releases real movement when controller resumes in the collision-free tavern", async ({ page }) => {
  test.setTimeout(45_000);
  const externalId = "e2e-nav-tavern-stall-player";
  await useIsolatedPlayer(page, externalId);
  await placePlayerInTavern(page, externalId);
  await page.goto("/");
  await expect(page.locator("body")).toHaveAttribute("data-scene", "tavern", { timeout: 10_000 });

  await page.evaluate(() => {
    const debugWindow = window as Window & {
      __navStallStart?: { x: number; y: number } | null;
      __navStallProbeInstalled?: boolean;
    };
    debugWindow.__navStallStart = null;
    if (debugWindow.__navStallProbeInstalled) return;
    debugWindow.__navStallProbeInstalled = true;
    window.addEventListener("keydown", (event) => {
      const key = event.key.toLowerCase();
      if (!new Set(["w", "a", "s", "d"]).has(key) || debugWindow.__navStallStart) return;
      debugWindow.__navStallStart = {
        x: Number(document.body.dataset.playerX),
        y: Number(document.body.dataset.playerY)
      };
    }, true);
  });

  let movementError: unknown = null;
  const movement = moveTowardInteraction(page, 650, 325, "поговорить с Ореном", 20_000)
    .catch((error) => {
      movementError = error;
    });

  try {
    await page.waitForFunction(() => {
      const debugWindow = window as Window & { __navStallStart?: { x: number; y: number } | null };
      return Boolean(debugWindow.__navStallStart);
    });

    const blockedUntil = Date.now() + 700;
    while (Date.now() < blockedUntil) {
      // Playwright's Node controller is deliberately unavailable. A real held key
      // therefore remains down in the independently rendering browser until the
      // controller resumes and can issue keyup. Continued travel during this window
      // is expected physical-keyboard semantics, not runaway input.
    }

    const stallTravel = await page.evaluate(() => {
      const debugWindow = window as Window & { __navStallStart?: { x: number; y: number } | null };
      const start = debugWindow.__navStallStart;
      if (!start) return 0;
      const current = {
        x: Number(document.body.dataset.playerX),
        y: Number(document.body.dataset.playerY)
      };
      return Math.hypot(current.x - start.x, current.y - start.y);
    });

    // Prove the test is exercising a real held key: the browser keeps moving while
    // its external controller is intentionally blocked.
    expect(stallTravel).toBeGreaterThan(10);

    await movement;
    if (movementError) throw movementError;
    await expect(page.locator("#interaction-hint")).toContainText("поговорить с Ореном");

    // The safety invariant belongs after controller recovery: once the helper has
    // returned, every real movement key must be up and the avatar must stop drifting.
    const stoppedAt = await page.evaluate(() => ({
      x: Number(document.body.dataset.playerX),
      y: Number(document.body.dataset.playerY)
    }));
    await page.waitForTimeout(250);
    const afterSettle = await page.evaluate(() => ({
      x: Number(document.body.dataset.playerX),
      y: Number(document.body.dataset.playerY)
    }));
    expect(Math.hypot(afterSettle.x - stoppedAt.x, afterSettle.y - stoppedAt.y)).toBeLessThan(2);
  } finally {
    await releaseMovementKeys(page);
    await movement.catch(() => undefined);
  }
});

test("canonical location change clears the previous NPC interaction immediately", async ({ page }) => {
  test.setTimeout(45_000);
  await useIsolatedPlayer(page, "e2e-nav-stale-player");
  await page.goto("/");
  const body = page.locator("body");
  const hint = page.locator("#interaction-hint");

  await expect(body).toHaveAttribute("data-canonical-location", "workshop_yard");
  await approachAndTalk(page, 250, 365, "поговорить с Мирой", "Мира");
  await page.getByRole("button", { name: "Закрыть", exact: true }).click();
  await expect(hint).toContainText("поговорить с Мирой", { timeout: 3_000 });

  await page.getByRole("button", { name: "Идти: площадь", exact: true }).click();
  await expect(body).toHaveAttribute("data-canonical-location", "village_square");

  await expect(hint).not.toContainText("поговорить с Мирой", { timeout: 150 });
  await page.keyboard.press("e");
  await expect(page.locator("#dialogue")).toBeHidden();
});