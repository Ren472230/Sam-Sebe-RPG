import { expect, test, type Page } from "@playwright/test";

import { installBrowserDiagnostics } from "./helpers/browser-diagnostics";

async function moveUntilHint(page: Page, keys: string[], text: string): Promise<void> {
  const hint = page.locator("#interaction-hint");
  for (let attempt = 0; attempt < 40; attempt += 1) {
    if ((await hint.textContent())?.includes(text)) return;
    for (const key of keys) {
      await page.keyboard.down(key);
      await page.waitForTimeout(70);
      await page.keyboard.up(key);
      await page.waitForTimeout(50);
      if ((await hint.textContent())?.includes(text)) return;
    }
  }
  await expect(hint).toContainText(text, { timeout: 1_000 });
}

async function moveByStepsUntilHint(page: Page, key: string, text: string): Promise<void> {
  const hint = page.locator("#interaction-hint");
  for (let attempt = 0; attempt < 40; attempt += 1) {
    if ((await hint.textContent())?.includes(text)) return;
    await page.keyboard.down(key);
    await page.waitForTimeout(70);
    await page.keyboard.up(key);
    await page.waitForTimeout(50);
  }
  await expect(hint).toContainText(text, { timeout: 1_000 });
}

async function putLocalPlayerInTavern(page: Page): Promise<void> {
  const session = await page.request.post("/api/session", {
    data: { external_id: "local-player", name: "Ren" }
  });
  expect(session.ok()).toBeTruthy();
  const playerId = (await session.json() as { player_id: string }).player_id;

  for (const destinationId of ["village_square", "tavern_interior"]) {
    const action = await page.request.post("/api/action", {
      data: {
        player_id: playerId,
        action_type: "MOVE",
        destination_id: destinationId,
        external_id: `mobile-hint-${destinationId}`
      }
    });
    expect(action.ok()).toBeTruthy();
    expect((await action.json() as { success: boolean }).success).toBeTruthy();
  }
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
  if (!path) throw new Error(`unsupported first-run location: ${state.location.id}`);

  for (const [index, destinationId] of path.entries()) {
    const action = await page.request.post("/api/action", {
      data: {
        player_id: playerId,
        action_type: "MOVE",
        destination_id: destinationId,
        external_id: `spatial-mira-reset-${index}-${destinationId}`
      }
    });
    expect(action.ok()).toBeTruthy();
    expect((await action.json() as { success: boolean }).success).toBeTruthy();
  }
}


test("normal mode gives the player a localized immediate goal and a presentation-ready title", async ({ page }, testInfo) => {
  const diagnostics = installBrowserDiagnostics(page);
  try {
    await page.goto("/");
    const hud = page.locator("#hud");

    await expect(page).toHaveTitle("Сам-себе-RPG");
    await expect(hud).toContainText("Цель:");
    await expect(hud).not.toContainText(/Workshop Yard|Village Square|River Edge|The Wayfarer's Hearth/);
    await expect(hud).toContainText("монеты");

    await page.screenshot({ path: "test-results/first-run-clarity.png", fullPage: true });
    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
  }
});


test("normal mode lets a human playtester download the current session report without developer tools", async ({ page }, testInfo) => {
  const diagnostics = installBrowserDiagnostics(page);
  try {
    await page.route("**/api/playtest/report/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session: "playtest-test-session",
          result: "FAIL",
          verdict: "NOT SAFE FOR HUMAN EXPERIENCE TEST",
          markdown: "# Отчёт игрового теста\n\nПроверка выгрузки текущей сессии.\n"
        })
      });
    });

    await page.goto("/");
    await expect(page.locator("body")).toHaveAttribute("data-playtest-session", /^playtest-/);
    const button = page.getByRole("button", { name: "Скачать отчёт теста", exact: true });
    await expect(button).toBeVisible();

    const downloadPromise = page.waitForEvent("download");
    await button.click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/^sam-sebe-rpg-playtest-.*\.md$/);
    await expect(page.locator("#playtest-export-status")).toContainText("Отчёт скачан");
    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
  }
});


test("390px viewport keeps touch controls reachable without a keyboard", async ({ page }, testInfo) => {
  const diagnostics = installBrowserDiagnostics(page);
  try {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    await expect(page.locator("#hud")).toContainText("Цель:");

    const layout = await page.evaluate(() => ({
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth
    }));

    expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewportWidth);
    expect(layout.bodyWidth).toBeLessThanOrEqual(layout.viewportWidth);
    await expect(page.locator("#game canvas")).toBeVisible();
    await expect(page.getByRole("button", { name: "Подождать 1 шаг", exact: true })).toBeVisible();

    const right = page.getByRole("button", { name: "Вправо", exact: true });
    const interact = page.getByRole("button", { name: "Взаимодействовать", exact: true });
    await expect(right).toBeVisible();
    await expect(interact).toBeVisible();

    const hint = page.locator("#interaction-hint");
    await expect(hint).toContainText("Экранные кнопки – движение · Действие – взаимодействие");
    await expect(hint).not.toContainText(/WASD|E —/);

    const controls = await page.evaluate(() => {
      const element = document.getElementById("touch-controls");
      if (!element) return null;
      const rect = element.getBoundingClientRect();
      return { top: rect.top, bottom: rect.bottom };
    });
    expect(controls).not.toBeNull();
    expect(controls!.top).toBeGreaterThanOrEqual(0);
    expect(controls!.bottom).toBeLessThanOrEqual(layout.viewportHeight);

    const before = Number(await page.locator("body").getAttribute("data-player-x"));
    await right.dispatchEvent("pointerdown", { pointerId: 1, pointerType: "touch", isPrimary: true });
    await page.waitForTimeout(180);
    await right.dispatchEvent("pointerup", { pointerId: 1, pointerType: "touch", isPrimary: true });
    await expect.poll(async () => Number(await page.locator("body").getAttribute("data-player-x"))).toBeGreaterThan(before);

    await page.screenshot({ path: "test-results/first-run-mobile-390.png", fullPage: true });
    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
  }
});


test("390px village uses the touch action label near firewood", async ({ page }, testInfo) => {
  const diagnostics = installBrowserDiagnostics(page);
  try {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    const hint = page.locator("#interaction-hint");

    await moveByStepsUntilHint(page, "a", "подобрать дрова");
    await expect(hint).toContainText("Действие – подобрать дрова");
    await expect(hint).not.toContainText(/E —/);
    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
  }
});


test("390px tavern uses the touch action label near Oren", async ({ page }, testInfo) => {
  const diagnostics = installBrowserDiagnostics(page);
  try {
    await page.setViewportSize({ width: 390, height: 844 });
    await putLocalPlayerInTavern(page);
    await page.goto("/");
    await expect(page.locator("body")).toHaveAttribute("data-scene", "tavern");
    const hint = page.locator("#interaction-hint");

    await moveUntilHint(page, ["w", "d"], "поговорить с Ореном");
    await expect(hint).toContainText("Действие – поговорить с Ореном");
    await expect(hint).not.toContainText(/E —/);
    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
  }
});


test("desktop player talks to Mira only after approaching her and can type Russian ы", async ({ page }, testInfo) => {
  const diagnostics = installBrowserDiagnostics(page);
  try {
    await putLocalPlayerInWorkshop(page);
    await page.goto("/");
    await expect(page.locator("body")).toHaveAttribute("data-scene", "village");
    await expect(page.locator("body")).toHaveAttribute("data-rendered-npc-ids", /npc_mira/);
    await expect(page.getByRole("button", { name: "Поговорить: Мира", exact: true })).toHaveCount(0);

    const hint = page.locator("#interaction-hint");
    await moveUntilHint(page, ["w", "a"], "поговорить с Мирой");
    await expect(hint).toContainText("поговорить с Мирой");
    await page.keyboard.press("e");

    const dialogue = page.locator("#dialogue");
    await expect(dialogue).toBeVisible();
    await expect(dialogue.locator("h2")).toHaveText("Мира");
    const input = dialogue.locator("textarea");
    await input.fill("Ты слышишь меня?");
    await expect(input).toHaveValue("Ты слышишь меня?");

    await page.screenshot({ path: "test-results/spatial-mira-dialogue.png", fullPage: true });
    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
  }
});
