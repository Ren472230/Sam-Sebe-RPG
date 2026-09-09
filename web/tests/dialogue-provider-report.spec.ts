import { expect, test, type Page } from "@playwright/test";

import { installBrowserDiagnostics } from "./helpers/browser-diagnostics";

type PlayerPosition = { x: number; y: number };
type DialogueReport = {
  dialogue: {
    responses_observed: number;
    neural_responses: number;
    fallback_responses: number;
  };
  markdown: string;
};

async function putLocalPlayerInTavern(page: Page): Promise<void> {
  const session = await page.request.post("/api/session", {
    data: { external_id: "local-player", name: "Ren" }
  });
  expect(session.ok()).toBeTruthy();
  const playerId = (await session.json() as { player_id: string }).player_id;
  const stateResponse = await page.request.get(`/api/state/${encodeURIComponent(playerId)}`);
  expect(stateResponse.ok()).toBeTruthy();
  const state = await stateResponse.json() as { location: { id: string } };

  const pathByLocation: Record<string, string[]> = {
    workshop_yard: ["village_square", "tavern_interior"],
    village_square: ["tavern_interior"],
    river_edge: ["village_square", "tavern_interior"],
    tavern_interior: []
  };
  const path = pathByLocation[state.location.id];
  if (!path) throw new Error(`unsupported dialogue-test location: ${state.location.id}`);

  for (const [index, destinationId] of path.entries()) {
    const action = await page.request.post("/api/action", {
      data: {
        player_id: playerId,
        action_type: "MOVE",
        destination_id: destinationId,
        external_id: `dialogue-provider-route-${index}-${destinationId}`
      }
    });
    expect(action.ok()).toBeTruthy();
    expect((await action.json() as { success: boolean }).success).toBeTruthy();
  }
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
  tolerance = 8,
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

test("a real NPC reply reaches the playtest report as neural-or-fallback metadata without dialogue text", async ({ page }, testInfo) => {
  test.setTimeout(45_000);
  const diagnostics = installBrowserDiagnostics(page);
  const privateLine = "Проверка провайдера ы 472230";

  try {
    await putLocalPlayerInTavern(page);
    await page.goto("/");
    const body = page.locator("body");
    await expect(body).toHaveAttribute("data-scene", "tavern");
    const sessionId = await body.getAttribute("data-playtest-session");
    expect(sessionId).toBeTruthy();

    await moveAxisTo(page, "x", 650);
    await moveAxisTo(page, "y", 325);
    await expect(page.locator("#interaction-hint")).toContainText("поговорить с Ореном");
    await page.keyboard.press("e");

    const dialogue = page.locator("#dialogue");
    await expect(dialogue).toBeVisible();
    await expect(dialogue.locator("h2")).toHaveText("Орен");
    const input = dialogue.locator("textarea");
    await input.fill(privateLine);
    await input.press("Enter");
    await expect(dialogue.locator(".dialogue-line-npc")).toHaveCount(1, { timeout: 10_000 });

    let latest: DialogueReport | null = null;
    await expect.poll(async () => {
      const response = await page.request.get(`/api/playtest/report/${encodeURIComponent(sessionId!)}`);
      if (!response.ok()) return 0;
      latest = await response.json() as DialogueReport;
      return latest.dialogue.responses_observed;
    }, { timeout: 10_000, intervals: [100, 250, 500] }).toBeGreaterThanOrEqual(1);

    expect(latest).not.toBeNull();
    expect(latest!.dialogue.neural_responses + latest!.dialogue.fallback_responses)
      .toBe(latest!.dialogue.responses_observed);
    expect(latest!.markdown).not.toContain(privateLine);
    expect(latest!.markdown).toContain("## DIALOGUE PROVIDER");

    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
  }
});
