import { expect, test } from "@playwright/test";

test("time controls wait for initial state before accepting a single WAIT action", async ({ page }) => {
  let holdingStartupState = true;
  let releaseInitialState!: () => void;
  const initialStateGate = new Promise<void>((resolve) => { releaseInitialState = resolve; });
  let reportInitialTick!: (tick: number) => void;
  const initialTickReady = new Promise<number>((resolve) => { reportInitialTick = resolve; });
  const actions: Record<string, unknown>[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && new URL(request.url()).pathname === "/api/action") {
      actions.push(request.postDataJSON());
    }
  });

  // Both the game and playtest recorder fetch initial state. Hold every startup
  // response so their request order cannot let bootstrap bypass the loading gate.
  await page.route("**/api/state/*", async (route) => {
    if (!holdingStartupState) {
      await route.continue();
      return;
    }
    const response = await route.fetch();
    const snapshot = await response.json();
    reportInitialTick(snapshot.world_pulse.tick);
    await initialStateGate;
    await route.fulfill({ response });
  });

  try {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const initialTick = await initialTickReady;
    const waitOne = page.getByRole("button", { name: "Подождать 1 шаг", exact: true });
    const waitFive = page.getByRole("button", { name: "Подождать 5 шагов", exact: true });
    await expect(waitOne).toBeVisible();
    await expect(waitFive).toBeVisible();
    await expect(waitOne).toBeDisabled();
    await expect(waitFive).toBeDisabled();
    expect(actions).toHaveLength(0);

    holdingStartupState = false;
    releaseInitialState();
    await expect(waitOne).toBeEnabled();
    await expect(waitFive).toBeEnabled();
    const actionResponseReady = page.waitForResponse((response) =>
      response.request().method() === "POST" && new URL(response.url()).pathname === "/api/action"
    );
    const updatedStateReady = page.waitForResponse(async (response) => {
      if (response.request().method() !== "GET"
        || !new URL(response.url()).pathname.startsWith("/api/state/")) return false;
      return response.ok() && (await response.json()).world_pulse.tick === initialTick + 5;
    });
    await waitFive.click();

    const actionResponse = await actionResponseReady;
    expect(actionResponse.ok()).toBeTruthy();
    expect(await actionResponse.json()).toMatchObject({ success: true });
    const updatedState = await updatedStateReady;
    expect(updatedState.ok()).toBeTruthy();
    expect((await updatedState.json()).world_pulse.tick).toBe(initialTick + 5);
    await expect(page.locator("#world-pulse-tick")).toHaveText(`Шаг ${initialTick + 5}`);
    await expect(waitOne).toBeEnabled();
    await expect(waitFive).toBeEnabled();
    expect(actions).toHaveLength(1);
    expect(actions[0]).toMatchObject({
      action_type: "WAIT",
      modifiers: { ticks: 5 },
      external_id: expect.any(String),
      player_id: expect.any(String)
    });
  } finally {
    holdingStartupState = false;
    releaseInitialState();
  }
});

test("world pulse turns waiting into a visible world change", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto("/");

  const pulse = page.locator("#world-pulse");
  const tick = pulse.locator("#world-pulse-tick");
  const nearby = pulse.locator("#world-pulse-nearby");
  const events = pulse.locator("#world-pulse-events li");
  const waitFive = pulse.getByRole("button", { name: "Подождать 5 шагов" });

  await expect(pulse).toBeVisible();
  await expect(pulse.getByRole("heading", { name: "Живой мир" })).toBeVisible();
  await expect(nearby).toContainText("Рядом:");
  await expect(nearby).not.toHaveText("Рядом: —");
  await expect(waitFive).toBeEnabled();

  const initialTickText = await tick.textContent();
  const initialTick = Number(initialTickText?.match(/\d+/)?.[0]);
  expect(Number.isInteger(initialTick)).toBeTruthy();

  await waitFive.click();

  await expect(tick).toHaveText(`Шаг ${initialTick + 5}`);
  await expect(events.first()).toBeVisible();
  const eventTexts = await events.allTextContents();
  expect(eventTexts.some((text) => /Мира|Каспар|Мир пока тих/.test(text))).toBeTruthy();
  expect(eventTexts.join(" ")).not.toMatch(/NPC_[A-Z_]+/);

  await page.screenshot({ path: "test-results/00-world-pulse.png", fullPage: true });
});
