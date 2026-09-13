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

test("controller stall cannot leave runaway movement active in the collision-free tavern", async ({ page }) => {
  test.setTimeout(45_000);
  await useIsolatedPlayer(page, "e2e-nav-tavern-stall-player");
  await page.goto("/");
  await expect(page.locator("body")).toHaveAttribute("data-scene", "village");
  await enterTavernSpatially(page);
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
      // The browser keeps rendering while the Playwright controller is deliberately unavailable.
    }

    const stallTravel = await page.evaluate(() => {
      const debugWindow = window as Window & { __navStallStart?: { x: number; y: number } | null };
      const start = debugWindow.__navStallStart;
      if (!start) return Number.POSITIVE_INFINITY;
      const current = {
        x: Number(document.body.dataset.playerX),
        y: Number(document.body.dataset.playerY)
      };
      return Math.hypot(current.x - start.x, current.y - start.y);
    });

    expect(stallTravel).toBeLessThan(55);
    await movement;
    if (movementError) throw movementError;
    await expect(page.locator("#interaction-hint")).toContainText("поговорить с Ореном");
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
