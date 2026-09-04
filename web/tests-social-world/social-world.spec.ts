import { expect, test, type Page } from "@playwright/test";

import { installBrowserDiagnostics } from "../tests/helpers/browser-diagnostics";

type SocialState = {
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

async function state(page: Page, playerId: string): Promise<SocialState> {
  const response = await page.request.get(`/api/state/${encodeURIComponent(playerId)}`);
  expect(response.ok()).toBeTruthy();
  return await response.json() as SocialState;
}

async function clickLivingAction(page: Page, label: string, expectedLocation?: string): Promise<void> {
  await page.getByRole("button", { name: label, exact: true }).click();
  if (expectedLocation) {
    await expect(page.locator("#hud")).toContainText(expectedLocation, { timeout: 10_000 });
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

async function waitOneTick(page: Page, playerId: string): Promise<void> {
  const before = (await state(page, playerId)).living_npc.tick;
  await page.getByRole("button", { name: "Подождать 1 шаг", exact: true }).click();
  await expect.poll(
    async () => (await state(page, playerId)).living_npc.tick,
    { timeout: 10_000 }
  ).toBe(before + 1);
}

async function talkToKaspar(page: Page, expected: RegExp | string): Promise<void> {
  await page.getByRole("button", { name: "Поговорить: Каспар", exact: true }).click();
  await expect(page.locator("#dialogue h2")).toHaveText("Каспар");
  await sendDialogue(page, "Что ты обо мне слышал?", expected);
}

test("Social World spreads Mira's report to Kaspar only after their real delivery contact and keeps it after reload", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  const diagnostics = installBrowserDiagnostics(page);

  try {
    await page.goto("/");
    await expect(page.locator("#hud")).toContainText("Workshop Yard");
    const playerId = await currentPlayerId(page);

    await page.getByRole("button", { name: "Подождать 5 шагов", exact: true }).click();
    await expect(page.locator("#world-pulse-tick")).toContainText("Шаг 5", { timeout: 10_000 });
    await expect(page.locator("#world-pulse-events")).toContainText("Мира просит древесину");

    await page.getByRole("button", { name: "Поговорить: Мира", exact: true }).click();
    await sendDialogue(page, "Я принесу тебе древесину.", /Договорились/i);
    await expect(page.locator("#dialogue small")).toContainText("социальная память");
    await page.getByRole("button", { name: "Закрыть", exact: true }).click();

    await clickLivingAction(page, "Идти: площадь", "Village Square");
    await clickLivingAction(page, "Идти: река", "River Edge");
    await expect(page.getByRole("button", { name: "Поговорить: Каспар", exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Поговорить: Каспар", exact: true }).click();
    await sendDialogue(page, "Что ты обо мне слышал?");
    await expect(page.locator("#dialogue")).not.toContainText("Мира говорила");
    await page.screenshot({ path: "test-results-social-world/social-01-pre-contact.png", fullPage: true });
    await page.getByRole("button", { name: "Закрыть", exact: true }).click();

    for (let step = 0; step < 4; step += 1) {
      await waitOneTick(page, playerId);
    }
    await expect(page.locator("#world-pulse-events")).toContainText("Каспар принёс древесину Мире", { timeout: 10_000 });

    const delivered = await state(page, playerId);
    expect(delivered.living_npc.tick).toBe(9);
    expect(delivered.living_npc.mira.requested_wood).toBe(false);
    expect(delivered.living_npc.kaspar.goal).toBeNull();

    await clickLivingAction(page, "Идти: площадь", "Village Square");
    await expect(page.getByRole("button", { name: "Поговорить: Каспар", exact: true })).toBeVisible();
    await talkToKaspar(page, /Мира говорила.*обещал.*древесин/i);
    await page.screenshot({ path: "test-results-social-world/social-02-post-contact.png", fullPage: true });
    await page.getByRole("button", { name: "Закрыть", exact: true }).click();

    await page.reload();
    await expect(page.locator("#hud")).toContainText("Village Square");
    expect(await currentPlayerId(page)).toBe(playerId);
    await expect(page.getByRole("button", { name: "Поговорить: Каспар", exact: true })).toBeVisible();
    await talkToKaspar(page, /Мира говорила.*обещал.*древесин/i);
    await page.screenshot({ path: "test-results-social-world/social-03-reloaded.png", fullPage: true });

    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
  }
});
