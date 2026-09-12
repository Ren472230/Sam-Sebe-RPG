import { expect, test, type Page } from "@playwright/test";

import { installBrowserDiagnostics } from "./helpers/browser-diagnostics";

type StatePayload = {
  player_id: string;
  location: { id: string };
  quest: {
    status: "available" | "active" | "completed";
    owned_firewood: number;
    required_firewood: number;
  };
  coins: number;
  oren_relation: { trust: number };
  world_pulse: { tick: number };
};

const EXPLORATORY_ACTIONS = 60;
const EXPLORATORY_SEED = 0x5a17c0de;

function seededRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 0x1_0000_0000;
  };
}

async function tapMovement(page: Page, random: () => number): Promise<void> {
  const keys = ["w", "a", "s", "d"] as const;
  const key = keys[Math.floor(random() * keys.length)]!;
  const duration = 70 + Math.floor(random() * 150);
  await page.keyboard.down(key);
  await page.waitForTimeout(duration);
  await page.keyboard.up(key);
  await page.waitForTimeout(40);
}

async function closeDialogueIfOpen(page: Page): Promise<boolean> {
  const dialogue = page.locator("#dialogue");
  if (!(await dialogue.isVisible())) return false;
  const close = page.getByRole("button", { name: "Закрыть" });
  if (await close.isVisible()) {
    await close.click();
    await expect(dialogue).toBeHidden();
  }
  return true;
}

async function safeInteraction(page: Page, random: () => number): Promise<void> {
  if (await closeDialogueIfOpen(page)) return;
  const hint = ((await page.locator("#interaction-hint").textContent()) ?? "").trim();
  if (/войти в таверну|выйти в деревню|поговорить с Ореном/i.test(hint)) {
    await page.keyboard.press("e");
    await page.waitForTimeout(150);
    return;
  }
  await tapMovement(page, random);
}

async function waitOneWorldStep(page: Page, random: () => number): Promise<void> {
  const button = page.getByRole("button", { name: "Подождать 1 шаг" });
  if (!(await button.isEnabled())) {
    await tapMovement(page, random);
    return;
  }
  const before = await worldTick(page);
  await button.click();
  await expect.poll(() => worldTick(page), { timeout: 10_000 }).toBe(before + 1);
}

async function worldTick(page: Page): Promise<number> {
  const text = (await page.locator("#world-pulse-tick").textContent()) ?? "";
  const match = text.match(/(\d+)/);
  if (!match) throw new Error(`world tick is unreadable: ${text}`);
  return Number(match[1]);
}

async function loadState(page: Page, playerId: string): Promise<StatePayload> {
  const response = await page.request.get(`/api/state/${encodeURIComponent(playerId)}`);
  expect(response.ok()).toBeTruthy();
  return await response.json() as StatePayload;
}

async function assertInvariants(page: Page, playerId: string, previousTick: number): Promise<number> {
  await expect(page.locator("#game canvas")).toBeVisible();
  await expect(page.locator("#hud")).toBeVisible();
  await expect(page.locator("body")).toHaveAttribute("data-scene", /^(village|tavern)$/);

  const position = await expect.poll(async () => page.evaluate(() => ({
    x: Number(document.body.dataset.playerX),
    y: Number(document.body.dataset.playerY)
  })), { timeout: 5_000 }).toEqual(expect.objectContaining({ x: expect.any(Number), y: expect.any(Number) }));
  void position;
  const actual = await page.evaluate(() => ({
    x: Number(document.body.dataset.playerX),
    y: Number(document.body.dataset.playerY)
  }));
  expect(Number.isFinite(actual.x)).toBe(true);
  expect(Number.isFinite(actual.y)).toBe(true);
  expect(actual.x).toBeGreaterThanOrEqual(0);
  expect(actual.x).toBeLessThanOrEqual(960);
  expect(actual.y).toBeGreaterThanOrEqual(0);
  expect(actual.y).toBeLessThanOrEqual(540);

  const state = await loadState(page, playerId);
  expect(state.player_id).toBe(playerId);
  expect(["available", "active", "completed"]).toContain(state.quest.status);
  expect(state.quest.required_firewood).toBe(5);
  expect(state.quest.owned_firewood).toBeGreaterThanOrEqual(0);
  expect(state.quest.owned_firewood).toBeLessThanOrEqual(5);
  expect(state.coins).toBeGreaterThanOrEqual(0);
  expect(Number.isFinite(state.oren_relation.trust)).toBe(true);
  expect(state.world_pulse.tick).toBeGreaterThanOrEqual(previousTick);
  return state.world_pulse.tick;
}

async function restoreWorkshop(page: Page, playerId: string): Promise<void> {
  let state = await loadState(page, playerId);
  const pathByLocation: Record<string, string[]> = {
    workshop_yard: [],
    village_square: ["workshop_yard"],
    river_edge: ["village_square", "workshop_yard"],
    tavern_interior: ["village_square", "workshop_yard"]
  };
  const path = pathByLocation[state.location.id];
  if (!path) throw new Error(`unsupported exploratory location: ${state.location.id}`);

  let step = 0;
  for (const destination of path) {
    const response = await page.request.post("/api/action", {
      data: {
        player_id: playerId,
        action_type: "MOVE",
        destination_id: destination,
        external_id: `explore-restore-${step}-${destination}`
      }
    });
    expect(response.ok()).toBeTruthy();
    const result = await response.json() as { success: boolean; code: string };
    expect(result.success, `restore move to ${destination}: ${result.code}`).toBe(true);
    step += 1;
  }
  state = await loadState(page, playerId);
  expect(state.location.id).toBe("workshop_yard");
}

test("deterministic exploratory route survives 60 sensible mixed actions", async ({ page }, testInfo) => {
  test.setTimeout(150_000);
  const diagnostics = installBrowserDiagnostics(page);
  const random = seededRandom(EXPLORATORY_SEED);

  try {
    await page.goto("/");
    await expect(page.locator("body")).toHaveAttribute("data-scene", /^(village|tavern)$/);
    await expect(page.locator("#game canvas")).toBeVisible();
    await page.screenshot({ path: "test-results/exploratory-01-start.png", fullPage: true });

    const session = await page.request.post("/api/session", {
      data: { external_id: "local-player", name: "Ren" }
    });
    expect(session.ok()).toBeTruthy();
    const { player_id: playerId } = await session.json() as { player_id: string };

    let lastTick = (await loadState(page, playerId)).world_pulse.tick;
    for (let index = 0; index < EXPLORATORY_ACTIONS; index += 1) {
      if (index === 19 || index === 39) {
        await page.reload();
        await expect(page.locator("body")).toHaveAttribute("data-scene", /^(village|tavern)$/);
        await expect(page.locator("#game canvas")).toBeVisible();
      } else {
        const choice = random();
        if (choice < 0.58) {
          await tapMovement(page, random);
        } else if (choice < 0.76) {
          await safeInteraction(page, random);
        } else if (choice < 0.90) {
          await waitOneWorldStep(page, random);
        } else {
          await closeDialogueIfOpen(page);
          await tapMovement(page, random);
        }
      }

      if ((index + 1) % 5 === 0 || index === EXPLORATORY_ACTIONS - 1) {
        lastTick = await assertInvariants(page, playerId, lastTick);
      }
    }

    await closeDialogueIfOpen(page);
    await restoreWorkshop(page, playerId);
    await page.reload();
    await expect(page.locator("body")).toHaveAttribute("data-scene", "village");
    const finalState = await loadState(page, playerId);
    expect(finalState.location.id).toBe("workshop_yard");
    expect(finalState.quest.status).toBe("available");
    expect(finalState.quest.owned_firewood).toBe(0);
    await page.screenshot({ path: "test-results/exploratory-02-end.png", fullPage: true });

    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
  }
});
