import { expect, test, type Page } from "@playwright/test";

import { installBrowserDiagnostics } from "../tests/helpers/browser-diagnostics";


type StreamState = {
  player_id: string;
  location: { id: string; name: string };
  living_npc: {
    tick: number;
    nearby_npc_ids: string[];
    mira: { location_id: string; wood_stock: number; requested_wood: boolean };
    kaspar: { location_id: string; goal: string | null; carrying_wood: number };
    driftwood: { location_id: string | null; owner_actor_id: string | null };
  };
};

type PlayerPosition = { x: number; y: number };

async function currentPlayerId(page: Page): Promise<string> {
  const response = await page.request.post("/api/session", {
    data: { external_id: "local-player", name: "Ren" }
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json() as { player_id: string }).player_id;
}

async function state(page: Page, playerId: string): Promise<StreamState> {
  const response = await page.request.get(`/api/state/${encodeURIComponent(playerId)}`);
  expect(response.ok()).toBeTruthy();
  return await response.json() as StreamState;
}

async function clickLivingAction(page: Page, label: string, expectedLocation?: string): Promise<void> {
  await page.getByRole("button", { name: label, exact: true }).click();
  if (expectedLocation) {
    await expect(page.locator("#hud")).toContainText(expectedLocation, { timeout: 10_000 });
    await expect(page.locator("#stream-status")).toContainText(`Место: ${expectedLocation}`, { timeout: 10_000 });
  }
}

async function sendDialogue(page: Page, text: string, expectedReply?: RegExp | string): Promise<void> {
  const input = page.locator(".dialogue-input");
  await input.fill(text);
  await input.press("Enter");
  if (expectedReply) {
    await expect(page.locator("#dialogue")).toContainText(expectedReply, { timeout: 10_000 });
  }
}

async function closeDialogue(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Закрыть", exact: true }).click();
}

async function waitOneTick(page: Page, playerId: string): Promise<void> {
  const before = (await state(page, playerId)).living_npc.tick;
  await page.getByRole("button", { name: "Подождать 1 шаг", exact: true }).click();
  await expect.poll(
    async () => (await state(page, playerId)).living_npc.tick,
    { timeout: 10_000 }
  ).toBe(before + 1);
}

async function playerPosition(page: Page): Promise<PlayerPosition> {
  return page.evaluate(() => ({
    x: Number(document.body.dataset.playerX),
    y: Number(document.body.dataset.playerY)
  }));
}

async function releaseMovementKeys(page: Page): Promise<void> {
  for (const key of ["w", "a", "s", "d"]) await page.keyboard.up(key);
  await page.waitForTimeout(50);
}

async function moveAxisTo(
  page: Page,
  axis: "x" | "y",
  target: number,
  tolerance = 9,
  timeout = 10_000
): Promise<void> {
  const started = Date.now();
  let heldKey: string | null = null;
  await releaseMovementKeys(page);
  try {
    while (Date.now() - started < timeout) {
      const position = await playerPosition(page);
      const value = position[axis];
      if (Number.isFinite(value) && Math.abs(value - target) <= tolerance) return;
      const key = axis === "x"
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
  throw new Error(`player did not reach ${axis}=${target}; last=${JSON.stringify(await playerPosition(page))}`);
}

async function moveTowardInteraction(
  page: Page,
  targetX: number,
  targetY: number,
  hintText: string,
  timeout = 20_000
): Promise<void> {
  const started = Date.now();
  const hint = page.locator("#interaction-hint");
  const axisDeadZone = 28;
  await releaseMovementKeys(page);

  while (Date.now() - started < timeout) {
    if ((await hint.textContent())?.includes(hintText)) return;

    const position = await playerPosition(page);
    const dx = targetX - position.x;
    const dy = targetY - position.y;
    const horizontal = dx >= 0 ? "d" : "a";
    const vertical = dy >= 0 ? "s" : "w";
    const keys: string[] = [];
    if (Math.abs(dx) > axisDeadZone) keys.push(horizontal);
    if (Math.abs(dy) > axisDeadZone) keys.push(vertical);
    if (keys.length === 0) keys.push(Math.abs(dx) >= Math.abs(dy) ? horizontal : vertical);

    try {
      for (const key of keys) await page.keyboard.down(key);
      await page.waitForTimeout(80);
    } finally {
      for (const key of keys) await page.keyboard.up(key);
    }
    await page.waitForTimeout(25);
  }

  await releaseMovementKeys(page);
  throw new Error(
    `player did not reach interaction ${JSON.stringify(hintText)} near (${targetX}, ${targetY}); last=${JSON.stringify(await playerPosition(page))}`
  );
}

async function approachAndTalk(
  page: Page,
  x: number,
  y: number,
  hint: string,
  heading: string
): Promise<void> {
  await moveTowardInteraction(page, x, y, hint);
  await expect(page.locator("#interaction-hint")).toContainText(hint, { timeout: 3_000 });
  await page.keyboard.press("e");
  await expect(page.locator("#dialogue")).toBeVisible({ timeout: 5_000 });
  await expect(page.locator("#dialogue h2")).toHaveText(heading);
}

async function enterTavernSpatially(page: Page): Promise<void> {
  await moveAxisTo(page, "x", 825);
  await moveAxisTo(page, "y", 325);
  await expect(page.locator("#interaction-hint")).toContainText("войти в таверну", { timeout: 3_000 });
  await page.keyboard.press("e");
  await expect(page.locator("body")).toHaveAttribute("data-scene", "tavern", { timeout: 10_000 });
  await expect(page.locator("body")).toHaveAttribute("data-rendered-tavern-npc-ids", /npc_oren/, { timeout: 10_000 });
}

async function exitTavernSpatially(page: Page): Promise<void> {
  await moveAxisTo(page, "x", 110);
  await moveAxisTo(page, "y", 420);
  await expect(page.locator("#interaction-hint")).toContainText("выйти в деревню", { timeout: 3_000 });
  await page.keyboard.press("e");
  await expect(page.locator("body")).toHaveAttribute("data-scene", "village", { timeout: 10_000 });
}


test("Stream Slice shows one causal evening, hospitality loop and persistence without leaking internals", async ({ page }, testInfo) => {
  test.setTimeout(180_000);
  const diagnostics = installBrowserDiagnostics(page);

  try {
    await page.goto("/?stream=1");
    await expect(page.locator("body")).toHaveClass(/stream-mode/);
    await expect(page.locator("#stream-status")).toBeVisible();
    await expect(page.locator("#stream-status")).toContainText(/Сейчас в деревне/i);
    await expect(page.locator("#stream-status")).toContainText("Место: Мастерская");
    await expect(page.locator("#stream-status")).not.toContainText(/npc_|source_knowledge_id|trust/i);
    await page.screenshot({ path: "test-results-stream-slice/stream-01-opening.png", fullPage: true });

    const playerId = await currentPlayerId(page);
    await page.getByRole("button", { name: "Подождать 5 шагов", exact: true }).click();
    await expect(page.locator("#world-pulse-tick")).toContainText("Шаг 5", { timeout: 10_000 });
    await expect(page.locator("#stream-status")).toContainText(/Мира просит древесину/i);

    await approachAndTalk(page, 250, 365, "поговорить с Мирой", "Мира");
    await sendDialogue(page, "Я принесу тебе древесину.", /Договорились/i);
    await closeDialogue(page);

    await clickLivingAction(page, "Идти: площадь", "Площадь");
    await clickLivingAction(page, "Идти: река", "Берег реки");
    await approachAndTalk(page, 610, 410, "поговорить с Каспаром", "Каспар");
    await sendDialogue(page, "Что ты обо мне слышал?");
    await expect(page.locator("#dialogue")).not.toContainText("Мира говорила");
    await closeDialogue(page);

    for (let step = 0; step < 4; step += 1) {
      await waitOneTick(page, playerId);
    }
    expect((await state(page, playerId)).living_npc.tick).toBe(9);
    await clickLivingAction(page, "Идти: площадь", "Площадь");
    await approachAndTalk(page, 610, 410, "поговорить с Каспаром", "Каспар");
    await sendDialogue(page, "Что ты обо мне слышал?", /Мира говорила.*обещал.*древесин/i);
    await page.screenshot({ path: "test-results-stream-slice/stream-02-kaspar-after-contact.png", fullPage: true });
    await closeDialogue(page);

    await waitOneTick(page, playerId);
    expect((await state(page, playerId)).living_npc.tick).toBe(10);
    await expect(page.locator("#stream-status")).toContainText(/Тален.*таверн|гост/i);
    await expect(page.locator("#stream-status")).toContainText(/Орен.*хлеб/i);

    await enterTavernSpatially(page);
    await expect(page.locator("body")).toHaveAttribute("data-rendered-tavern-npc-ids", /npc_wayfarer_1/);
    await approachAndTalk(page, 500, 385, "поговорить с Таленом", "Тален");
    await sendDialogue(page, "Что случилось в дороге?", /восточн.*караван/i);
    await expect(page.locator("#dialogue")).not.toContainText(/локальная реплика|AI-реплика|социальная память/i);
    await page.screenshot({ path: "test-results-stream-slice/stream-03-wayfarer.png", fullPage: true });
    await closeDialogue(page);

    await approachAndTalk(page, 650, 325, "поговорить с Ореном", "Орен");
    await sendDialogue(page, "Что рассказал Тален?", /Тален.*восточн.*караван/i);
    await sendDialogue(page, "Нужна помощь с гостем?", /хлеб/i);
    await page.screenshot({ path: "test-results-stream-slice/stream-04-oren-bread.png", fullPage: true });
    await closeDialogue(page);

    await exitTavernSpatially(page);
    await clickLivingAction(page, "Идти: площадь", "Площадь");
    await page.getByRole("button", { name: "Подобрать хлеб", exact: true }).click();
    await enterTavernSpatially(page);
    await page.getByRole("button", { name: "Отдать хлеб Орену", exact: true }).click();

    await approachAndTalk(page, 650, 325, "поговорить с Ореном", "Орен");
    await sendDialogue(page, "Хлеб подошёл?", /спасибо|хлеб|гост/i);
    await closeDialogue(page);

    await page.reload();
    await expect(page.locator("body")).toHaveClass(/stream-mode/);
    expect(await currentPlayerId(page)).toBe(playerId);
    await expect(page.locator("body")).toHaveAttribute("data-scene", "tavern");
    await approachAndTalk(page, 650, 325, "поговорить с Ореном", "Орен");
    await sendDialogue(page, "Что рассказал Тален?", /Тален.*караван/i);
    await page.screenshot({ path: "test-results-stream-slice/stream-05-reloaded.png", fullPage: true });

    await expect(page.locator("#stream-status")).not.toContainText(/npc_|source_knowledge_id|trust\s*:/i);
    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
  }
});