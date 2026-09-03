import { expect, test, type Page } from "@playwright/test";

import { installBrowserDiagnostics } from "../tests/helpers/browser-diagnostics";

type LivingState = {
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

async function currentPlayerId(page: Page): Promise<string> {
  const response = await page.request.post("/api/session", {
    data: { external_id: "local-player", name: "Ren" }
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json() as { player_id: string }).player_id;
}

async function state(page: Page, playerId: string): Promise<LivingState> {
  const response = await page.request.get(`/api/state/${encodeURIComponent(playerId)}`);
  expect(response.ok()).toBeTruthy();
  return await response.json() as LivingState;
}

async function clickLivingAction(page: Page, label: string, expectedLocation?: string): Promise<void> {
  await page.getByRole("button", { name: label, exact: true }).click();
  if (expectedLocation) {
    await expect(page.locator("#hud")).toContainText(expectedLocation, { timeout: 10_000 });
  }
}

async function sendDialogue(page: Page, text: string, expectedReply: RegExp | string): Promise<void> {
  const input = page.locator(".dialogue-input");
  await input.fill(text);
  await input.press("Enter");
  await expect(page.locator("#dialogue")).toContainText(expectedReply, { timeout: 10_000 });
}

test("Living NPC browser route remembers a commitment and lets the player beat Kaspar to Mira's wood problem", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  const diagnostics = installBrowserDiagnostics(page);

  try {
    await page.goto("/");
    await expect(page.locator("#hud")).toContainText("Workshop Yard");
    await expect(page.getByRole("button", { name: "Поговорить: Мира", exact: true })).toBeVisible();
    const playerId = await currentPlayerId(page);

    await page.getByRole("button", { name: "Подождать 5 шагов", exact: true }).click();
    await expect(page.locator("#world-pulse-tick")).toContainText("Шаг 5", { timeout: 10_000 });
    await expect(page.locator("#world-pulse-events")).toContainText("Мира просит древесину");

    await page.getByRole("button", { name: "Поговорить: Мира", exact: true }).click();
    await expect(page.locator("#dialogue h2")).toHaveText("Мира");
    await sendDialogue(page, "Что случилось?", /Работа встала/i);
    await sendDialogue(page, "Я принесу тебе древесину.", /Договорились/i);
    await expect(page.locator("#dialogue small")).toContainText("социальная память");
    await page.screenshot({ path: "test-results/living-npc-01-mira-commitment.png", fullPage: true });
    await page.getByRole("button", { name: "Закрыть", exact: true }).click();

    let snapshot = await state(page, playerId);
    expect(snapshot.living_npc.mira.requested_wood).toBe(true);
    expect(snapshot.living_npc.driftwood.location_id).toBe("river_edge");
    expect(snapshot.living_npc.driftwood.owner_actor_id).toBeNull();

    await clickLivingAction(page, "Идти: площадь", "Village Square");
    await clickLivingAction(page, "Идти: река", "River Edge");
    await expect(page.getByRole("button", { name: "Поговорить: Каспар", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Подобрать корягу", exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Поговорить: Каспар", exact: true }).click();
    await expect(page.locator("#dialogue h2")).toHaveText("Каспар");
    await expect(page.locator("#dialogue")).not.toContainText("Я принесу тебе древесину");
    await sendDialogue(page, "Что здесь происходит?", /дело|берег|древес/i);
    await expect(page.locator("#dialogue")).not.toContainText("Я принесу тебе древесину");
    await page.getByRole("button", { name: "Закрыть", exact: true }).click();

    await clickLivingAction(page, "Подобрать корягу");
    await expect.poll(async () => (await state(page, playerId)).living_npc.driftwood.owner_actor_id).toBe(playerId);

    await clickLivingAction(page, "Идти: площадь", "Village Square");
    await clickLivingAction(page, "Идти: мастерская", "Workshop Yard");
    await expect(page.getByRole("button", { name: "Отдать корягу Мире", exact: true })).toBeVisible();
    await clickLivingAction(page, "Отдать корягу Мире");

    await expect.poll(async () => (await state(page, playerId)).living_npc.mira.requested_wood).toBe(false);
    snapshot = await state(page, playerId);
    expect(snapshot.living_npc.mira.wood_stock).toBe(1);
    expect(snapshot.living_npc.kaspar.goal).toBeNull();
    expect(snapshot.living_npc.driftwood.location_id).toBeNull();
    expect(snapshot.living_npc.driftwood.owner_actor_id).toBeNull();

    await page.getByRole("button", { name: "Поговорить: Мира", exact: true }).click();
    await sendDialogue(page, "Ну что, теперь можешь работать?", /Пока всё идёт|работ/i);
    await expect(page.locator("#dialogue")).not.toContainText("Работа встала");
    await page.screenshot({ path: "test-results/living-npc-02-resolved.png", fullPage: true });
    await page.getByRole("button", { name: "Закрыть", exact: true }).click();

    await page.reload();
    await expect(page.locator("#hud")).toContainText("Workshop Yard");
    const samePlayerId = await currentPlayerId(page);
    expect(samePlayerId).toBe(playerId);
    const reloaded = await state(page, playerId);
    expect(reloaded.living_npc.mira.requested_wood).toBe(false);
    expect(reloaded.living_npc.mira.wood_stock).toBe(1);
    await expect(page.getByRole("button", { name: "Поговорить: Мира", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Поговорить: Мира", exact: true }).click();
    await sendDialogue(page, "Можешь продолжать работу?", /Пока всё идёт|работ/i);
    await page.screenshot({ path: "test-results/living-npc-03-reloaded.png", fullPage: true });

    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
  }
});
