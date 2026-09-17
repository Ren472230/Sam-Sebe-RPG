import { expect, test, type Page } from "@playwright/test";

import { installBrowserDiagnostics } from "../tests/helpers/browser-diagnostics";

type PlayerPosition = { x: number; y: number };

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

async function putLocalPlayerInWorkshop(page: Page): Promise<void> {
  const session = await page.request.post("/api/session", {
    data: { external_id: "local-player", name: "Ren" }
  });
  expect(session.ok()).toBeTruthy();
  const playerId = (await session.json() as { player_id: string }).player_id;
  const stateResponse = await page.request.get(`/api/state/${encodeURIComponent(playerId)}`);
  expect(stateResponse.ok()).toBeTruthy();
  const state = await stateResponse.json() as { location: { id: string } };

  const pathByLocation: Record<string, string[]> = {
    workshop_yard: [],
    village_square: ["workshop_yard"],
    river_edge: ["village_square", "workshop_yard"],
    tavern_interior: ["village_square", "workshop_yard"]
  };
  const path = pathByLocation[state.location.id];
  if (!path) throw new Error(`unsupported rehearsal location: ${state.location.id}`);

  for (const [index, destinationId] of path.entries()) {
    const action = await page.request.post("/api/action", {
      data: {
        player_id: playerId,
        action_type: "MOVE",
        destination_id: destinationId,
        external_id: `prestream-rehearsal-reset-${index}-${destinationId}-${Date.now()}`
      }
    });
    expect(action.ok()).toBeTruthy();
    expect((await action.json() as { success: boolean }).success).toBeTruthy();
  }
}

test("pre-stream human-control rehearsal keeps dialogue modal under messy keyboard input", async ({ page }, testInfo) => {
  test.setTimeout(60_000);
  const diagnostics = installBrowserDiagnostics(page);

  try {
    await putLocalPlayerInWorkshop(page);
    await page.goto("/?stream=1");
    await expect(page.locator("body")).toHaveAttribute("data-scene", "village");
    await expect(page.locator("body")).toHaveAttribute("data-rendered-npc-ids", /npc_mira/);

    await moveAxisTo(page, "y", 365);
    await moveAxisTo(page, "x", 250);
    await expect(page.locator("#interaction-hint")).toContainText("поговорить с Мирой", { timeout: 3_000 });
    await page.keyboard.press("e");

    const dialogue = page.locator("#dialogue");
    const input = dialogue.locator("textarea");
    await expect(dialogue).toBeVisible();
    await expect(dialogue.locator("h2")).toHaveText("Мира");
    await expect(input).toBeFocused();

    const draft = "Черновик: ыыы. Я ещё думаю.";
    await input.fill(draft);
    const beforeFocusedKey = await playerPosition(page);
    await page.keyboard.press("s");
    await page.waitForTimeout(150);
    expect(await playerPosition(page)).toEqual(beforeFocusedKey);
    await expect(input).toHaveValue(`${draft}s`);

    await dialogue.locator("h2").click();
    await expect(input).not.toBeFocused();
    const preservedDraft = await input.inputValue();
    const beforeBlurredStress = await playerPosition(page);

    await page.keyboard.down("d");
    await page.waitForTimeout(250);
    await page.keyboard.up("d");
    for (let attempt = 0; attempt < 5; attempt += 1) {
      await page.keyboard.press("e");
      await page.waitForTimeout(35);
    }
    await page.waitForTimeout(150);

    expect(await playerPosition(page)).toEqual(beforeBlurredStress);
    await expect(dialogue).toBeVisible();
    await expect(dialogue.locator("h2")).toHaveText("Мира");
    await expect(dialogue.locator("textarea")).toHaveValue(preservedDraft);

    await page.screenshot({
      path: "test-results-stream-slice/prestream-human-control-rehearsal.png",
      fullPage: true
    });

    await page.getByRole("button", { name: "Закрыть", exact: true }).click();
    await expect(dialogue).toBeHidden();
    const beforeResume = await playerPosition(page);
    await page.keyboard.down("d");
    await page.waitForTimeout(220);
    await page.keyboard.up("d");
    await expect.poll(async () => (await playerPosition(page)).x).toBeGreaterThan(beforeResume.x);

    diagnostics.assertClean();
  } finally {
    await releaseMovementKeys(page);
    await diagnostics.attach(testInfo);
  }
});
