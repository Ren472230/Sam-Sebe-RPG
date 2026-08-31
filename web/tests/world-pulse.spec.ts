import { expect, test } from "@playwright/test";

test("world pulse turns waiting into a visible world change", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto("/");

  const pulse = page.locator("#world-pulse");
  const tick = pulse.locator("#world-pulse-tick");
  const nearby = pulse.locator("#world-pulse-nearby");
  const events = pulse.locator("#world-pulse-events li");

  await expect(pulse).toBeVisible();
  await expect(pulse.getByRole("heading", { name: "Живой мир" })).toBeVisible();
  await expect(nearby).toContainText("Рядом:");

  const initialTickText = await tick.textContent();
  const initialTick = Number(initialTickText?.match(/\d+/)?.[0]);
  expect(Number.isInteger(initialTick)).toBeTruthy();

  await pulse.getByRole("button", { name: "Подождать 5 шагов" }).click();

  await expect(tick).toHaveText(`Шаг ${initialTick + 5}`);
  await expect(events.first()).toBeVisible();
  const eventTexts = await events.allTextContents();
  expect(eventTexts.some((text) => /Мира|Каспар|Мир пока тих/.test(text))).toBeTruthy();
  expect(eventTexts.join(" ")).not.toMatch(/NPC_[A-Z_]+/);

  await page.screenshot({ path: "test-results/00-world-pulse.png", fullPage: true });
});
