import { expect, test, type Page } from "@playwright/test";

import { installBrowserDiagnostics } from "../tests/helpers/browser-diagnostics";
import {
  approachAndTalk,
  enterTavernSpatially,
  exitTavernSpatially
} from "../tests/helpers/spatial-navigation";


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

async function measuredStep<T>(title: string, body: () => Promise<T>): Promise<T> {
  const started = Date.now();
  try {
    return await test.step(title, body);
  } finally {
    console.log(`[stream-step] ${title}: ${Date.now() - started}ms`);
  }
}

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

async function enterStreamTavern(page: Page): Promise<void> {
  await enterTavernSpatially(page);
  await expect(page.locator("body")).toHaveAttribute("data-rendered-tavern-npc-ids", /npc_oren/, { timeout: 10_000 });
}


test("Stream Slice shows one causal evening, hospitality loop and persistence without leaking internals", async ({ page }, testInfo) => {
  test.setTimeout(180_000);
  const diagnostics = installBrowserDiagnostics(page);

  try {
    const playerId = await measuredStep("boot, world advance and Mira commitment", async () => {
      await page.goto("/?stream=1");
      await expect(page.locator("body")).toHaveClass(/stream-mode/);
      await expect(page.locator("#stream-status")).toBeVisible();
      await expect(page.locator("#stream-status")).toContainText(/Сейчас в деревне/i);
      await expect(page.locator("#stream-status")).toContainText("Место: Мастерская");
      await expect(page.locator("#stream-status")).not.toContainText(/npc_|source_knowledge_id|trust/i);
      await page.screenshot({ path: "test-results-stream-slice/stream-01-opening.png", fullPage: true });

      const id = await currentPlayerId(page);
      await page.getByRole("button", { name: "Подождать 5 шагов", exact: true }).click();
      await expect(page.locator("#world-pulse-tick")).toContainText("Шаг 5", { timeout: 10_000 });
      await expect(page.locator("#stream-status")).toContainText(/Мира просит древесину/i);

      await approachAndTalk(page, 250, 365, "поговорить с Мирой", "Мира");
      await sendDialogue(page, "Я принесу тебе древесину.", /Договорились/i);
      await closeDialogue(page);
      return id;
    });

    await measuredStep("Kaspar before social contact", async () => {
      await clickLivingAction(page, "Идти: площадь", "Площадь");
      await clickLivingAction(page, "Идти: река", "Берег реки");
      await approachAndTalk(page, 610, 410, "поговорить с Каспаром", "Каспар");
      await sendDialogue(page, "Что ты обо мне слышал?");
      await expect(page.locator("#dialogue")).not.toContainText("Мира говорила");
      await closeDialogue(page);
    });

    await measuredStep("advance to real contact and verify propagated knowledge", async () => {
      for (let step = 0; step < 4; step += 1) {
        await waitOneTick(page, playerId);
      }
      expect((await state(page, playerId)).living_npc.tick).toBe(9);
      await clickLivingAction(page, "Идти: площадь", "Площадь");
      await approachAndTalk(page, 610, 410, "поговорить с Каспаром", "Каспар");
      await sendDialogue(page, "Что ты обо мне слышал?", /Мира говорила.*обещал.*древесин/i);
      await page.screenshot({ path: "test-results-stream-slice/stream-02-kaspar-after-contact.png", fullPage: true });
      await closeDialogue(page);
    });

    await measuredStep("hospitality arrival, tavern entry and conversations", async () => {
      await waitOneTick(page, playerId);
      expect((await state(page, playerId)).living_npc.tick).toBe(10);
      await expect(page.locator("#stream-status")).toContainText(/Тален.*таверн|гост/i);
      await expect(page.locator("#stream-status")).toContainText(/Орен.*хлеб/i);

      await enterStreamTavern(page);
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
    });

    await measuredStep("bread pickup and delivery", async () => {
      await exitTavernSpatially(page);
      await clickLivingAction(page, "Идти: площадь", "Площадь");
      await page.getByRole("button", { name: "Подобрать хлеб", exact: true }).click();
      await enterStreamTavern(page);
      await page.getByRole("button", { name: "Отдать хлеб Орену", exact: true }).click();

      await approachAndTalk(page, 650, 325, "поговорить с Ореном", "Орен");
      await sendDialogue(page, "Хлеб подошёл?", /спасибо|хлеб|гост/i);
      await closeDialogue(page);
    });

    await measuredStep("reload and persistence verification", async () => {
      await page.reload();
      await expect(page.locator("body")).toHaveClass(/stream-mode/);
      expect(await currentPlayerId(page)).toBe(playerId);
      await expect(page.locator("body")).toHaveAttribute("data-scene", "tavern");
      await approachAndTalk(page, 650, 325, "поговорить с Ореном", "Орен");
      await sendDialogue(page, "Что рассказал Тален?", /Тален.*караван/i);
      await page.screenshot({ path: "test-results-stream-slice/stream-05-reloaded.png", fullPage: true });

      await expect(page.locator("#stream-status")).not.toContainText(/npc_|source_knowledge_id|trust\s*:/i);
    });

    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
  }
});
