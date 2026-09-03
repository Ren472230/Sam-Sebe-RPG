import { mkdir, writeFile } from "node:fs/promises";

import { expect, test, type Page } from "@playwright/test";

import { installBrowserDiagnostics } from "./helpers/browser-diagnostics";

type PlayerPosition = { x: number; y: number };
type ActionPayload = {
  success: boolean;
  code: string;
  summary: string;
  event_id: number | null;
  replayed: boolean;
};
type PlaytestReport = {
  result: "PASS" | "FAIL";
  verdict: string;
  markdown: string;
  living_world: { steps_advanced: number; meaningful_events_observed: number };
  errors: {
    expected_gameplay_failures: number;
    unexpected_backend_failures: number;
    client_errors: number;
    console_errors: number;
    crashes: number;
  };
};

async function playerPosition(page: Page): Promise<PlayerPosition> {
  return page.evaluate(() => ({
    x: Number(document.body.dataset.playerX),
    y: Number(document.body.dataset.playerY)
  }));
}

async function releaseMovementKeys(page: Page): Promise<void> {
  for (const key of ["w", "a", "s", "d"]) {
    await page.keyboard.up(key);
  }
  await page.waitForTimeout(60);
}

async function moveAxisTo(
  page: Page,
  axis: "x" | "y",
  target: number,
  tolerance = 12,
  timeout = 12_000
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
      await page.waitForTimeout(100);
    }
  } finally {
    if (heldKey) await page.keyboard.up(heldKey);
    await releaseMovementKeys(page);
  }
  throw new Error(`player did not reach ${axis}=${target}; last=${JSON.stringify(await playerPosition(page))}`);
}

async function moveAndInteractWhenHint(
  page: Page,
  keys: string[],
  hintText: string,
  timeout = 10_000
): Promise<void> {
  const hint = page.locator("#interaction-hint");
  await releaseMovementKeys(page);
  for (const key of keys) await page.keyboard.down(key);
  try {
    await expect(hint).toContainText(hintText, { timeout });
    await page.keyboard.press("e");
  } finally {
    for (const key of keys) await page.keyboard.up(key);
    await releaseMovementKeys(page);
  }
}

async function enterTavernFromVillage(page: Page): Promise<void> {
  await moveAxisTo(page, "x", 936, 4);
  await moveAndInteractWhenHint(page, ["w", "a"], "войти в таверну");
  await expect(page.locator("body")).toHaveAttribute("data-scene", "tavern");
}

async function approachOren(page: Page): Promise<void> {
  await moveAndInteractWhenHint(page, ["w", "d"], "поговорить с Ореном");
  await expect(page.locator("#dialogue")).toBeVisible();
  await expect(page.locator("#dialogue h2")).toHaveText("Орен");
}

async function leaveTavern(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Закрыть" }).click().catch(() => undefined);
  await moveAndInteractWhenHint(page, ["s", "a"], "выйти в деревню");
  await expect(page.locator("body")).toHaveAttribute("data-scene", "village");
}

async function collectOneFirewood(page: Page, expectedCount: number): Promise<void> {
  const hint = page.locator("#interaction-hint");
  const targetXs = [260, 224, 188, 151, 112];
  const targetX = targetXs[expectedCount - 1];
  if (targetX === undefined) throw new Error(`unsupported firewood count: ${expectedCount}`);

  await moveAxisTo(page, "x", targetX, 8);
  await expect(hint).toContainText("подобрать дрова", { timeout: 10_000 });
  await page.keyboard.press("e");
  await releaseMovementKeys(page);
  await expect(page.locator("#hud")).toContainText(`дрова ${expectedCount}/5`);
}

async function readWorldTick(page: Page): Promise<number> {
  const text = (await page.locator("#world-pulse-tick").textContent()) ?? "";
  const match = text.match(/(\d+)/);
  if (!match) throw new Error(`world tick is unreadable: ${text}`);
  return Number(match[1]);
}

async function waitThroughUi(page: Page, ticks: 1 | 5, expectedTick: number): Promise<void> {
  await page.getByRole("button", { name: `Подождать ${ticks} ${ticks === 1 ? "шаг" : "шагов"}` }).click();
  await expect.poll(() => readWorldTick(page), { timeout: 10_000 }).toBe(expectedTick);
}

async function verifyLivingWorldApi(page: Page): Promise<void> {
  const session = await page.request.post("/api/session", {
    data: { external_id: "browser-world-probe", name: "World Probe" }
  });
  expect(session.ok()).toBeTruthy();
  const { player_id: playerId } = await session.json() as { player_id: string };

  const waitOneResponse = await page.request.post("/api/action", {
    data: {
      player_id: playerId,
      action_type: "WAIT",
      modifiers: { ticks: 1 },
      external_id: "browser-wait-1"
    }
  });
  expect(waitOneResponse.ok()).toBeTruthy();
  const waitOne = await waitOneResponse.json() as ActionPayload;
  expect(waitOne.success).toBe(true);
  expect(waitOne.code).toBe("OK");
  expect(waitOne.replayed).toBe(false);

  const waitNineResponse = await page.request.post("/api/action", {
    data: {
      player_id: playerId,
      action_type: "WAIT",
      modifiers: { ticks: 9 },
      external_id: "browser-wait-9"
    }
  });
  expect(waitNineResponse.ok()).toBeTruthy();
  const waitNine = await waitNineResponse.json() as ActionPayload;
  expect(waitNine.success).toBe(true);
  expect(waitNine.code).toBe("OK");
  expect(waitNine.replayed).toBe(false);

  const replayResponse = await page.request.post("/api/action", {
    data: {
      player_id: playerId,
      action_type: "WAIT",
      modifiers: { ticks: 9 },
      external_id: "browser-wait-9"
    }
  });
  expect(replayResponse.ok()).toBeTruthy();
  const replay = await replayResponse.json() as ActionPayload;
  expect(replay.success).toBe(true);
  expect(replay.replayed).toBe(true);
  expect(replay.event_id).toBe(waitNine.event_id);
}

async function fetchPassingReport(page: Page, sessionId: string): Promise<PlaytestReport> {
  const commit = process.env.GITHUB_SHA ?? "local";
  const url = `/api/playtest/report/${encodeURIComponent(sessionId)}?commit=${encodeURIComponent(commit)}`;
  await expect.poll(async () => {
    const response = await page.request.get(url);
    if (!response.ok()) return `HTTP ${response.status()}`;
    const payload = await response.json() as PlaytestReport;
    return payload.result;
  }, { timeout: 10_000, intervals: [100, 250, 500] }).toBe("PASS");

  const response = await page.request.get(url);
  expect(response.ok()).toBeTruthy();
  return await response.json() as PlaytestReport;
}

test("canonical route finishes the firewood quest, advances the Living World, persists, and emits a PASS report", async ({ page }, testInfo) => {
  test.setTimeout(150_000);
  const diagnostics = installBrowserDiagnostics(page);
  try {
    await page.goto("/");
    const body = page.locator("body");
    await expect(body).toHaveAttribute("data-scene", "village");
    await expect(body).toHaveAttribute("data-playtest-session", /^playtest-/);
    const sessionId = await body.getAttribute("data-playtest-session");
    expect(sessionId).toBeTruthy();

    await expect(body).toHaveAttribute("data-art-mode", "prototype");
    await expect(body).toHaveAttribute("data-village-art", "prototype");
    await expect(body).toHaveAttribute("data-player-art", "prototype");
    await expect(body).toHaveAttribute("data-firewood-art", "prototype");
    await expect(page.locator("#hud")).toContainText("Workshop Yard");
    await page.screenshot({ path: "test-results/01-village.png", fullPage: true });

    await enterTavernFromVillage(page);
    await expect(body).toHaveAttribute("data-tavern-art", "prototype");
    await approachOren(page);
    await expect(page.getByRole("button", { name: "Взяться за дрова" })).toBeVisible();
    await page.screenshot({ path: "test-results/02-oren-offer.png", fullPage: true });
    await page.getByRole("button", { name: "Взяться за дрова" }).click();
    await expect(page.locator("#hud")).toContainText("дрова 0/5");
    await page.screenshot({ path: "test-results/03-active-quest.png", fullPage: true });

    await leaveTavern(page);
    for (let count = 1; count <= 4; count += 1) {
      await collectOneFirewood(page, count);
    }
    await page.screenshot({ path: "test-results/04-four-firewood.png", fullPage: true });

    await enterTavernFromVillage(page);
    await approachOren(page);
    await page.getByRole("button", { name: "Передать дрова" }).click();
    await expect(page.locator("#dialogue")).toContainText("Oren still needs 1 more firewood.");
    await page.screenshot({ path: "test-results/05-correct-early-rejection.png", fullPage: true });

    await leaveTavern(page);
    await collectOneFirewood(page, 5);

    await enterTavernFromVillage(page);
    await approachOren(page);
    await page.getByRole("button", { name: "Передать дрова" }).click();
    await expect(page.locator("#hud")).toContainText("дрова доставлены ✓");
    await expect(page.locator("#hud")).toContainText("монеты 15");
    await expect(page.locator("#hud")).toContainText("доверие Орена 10");
    await expect(page.locator("#dialogue")).toContainText("помню, что ты выручил меня");
    await page.screenshot({ path: "test-results/06-completed.png", fullPage: true });

    await page.reload();
    await expect(body).toHaveAttribute("data-scene", "tavern");
    await expect(body).toHaveAttribute("data-playtest-session", sessionId!);
    await expect(page.locator("#hud")).toContainText("дрова доставлены ✓");
    await expect(page.locator("#hud")).toContainText("монеты 15");
    await expect(page.locator("#hud")).toContainText("доверие Орена 10");
    await page.screenshot({ path: "test-results/07-reloaded.png", fullPage: true });

    const tickBefore = await readWorldTick(page);
    await waitThroughUi(page, 1, tickBefore + 1);
    await waitThroughUi(page, 5, tickBefore + 6);
    await expect(page.locator("#world-pulse-events li").first()).not.toHaveText("Мир пока тих.");
    await page.screenshot({ path: "test-results/08-living-world.png", fullPage: true });

    const report = await fetchPassingReport(page, sessionId!);
    expect(report.verdict).toBe("SAFE FOR HUMAN EXPERIENCE TEST");
    expect(report.living_world.steps_advanced).toBe(6);
    expect(report.living_world.meaningful_events_observed).toBeGreaterThan(0);
    expect(report.errors.expected_gameplay_failures).toBe(1);
    expect(report.errors.unexpected_backend_failures).toBe(0);
    expect(report.errors.client_errors).toBe(0);
    expect(report.errors.console_errors).toBe(0);
    expect(report.errors.crashes).toBe(0);

    await mkdir("test-results", { recursive: true });
    await writeFile("test-results/autonomous-playtest-report.json", `${JSON.stringify(report, null, 2)}\n`, "utf8");
    await writeFile("test-results/autonomous-playtest-report.md", report.markdown, "utf8");
    await testInfo.attach("autonomous-playtest-report.json", {
      body: Buffer.from(JSON.stringify(report, null, 2), "utf8"),
      contentType: "application/json"
    });
    await testInfo.attach("autonomous-playtest-report.md", {
      body: Buffer.from(report.markdown, "utf8"),
      contentType: "text/markdown"
    });

    await verifyLivingWorldApi(page);
    diagnostics.assertClean();
  } finally {
    await diagnostics.attach(testInfo);
  }
});
