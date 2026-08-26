import { expect, test } from "@playwright/test";

test("backend unavailable is surfaced as a readable startup error", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.route("**/api/session", async (route) => {
    await route.abort("failed");
  });

  await page.goto("/");
  await expect(page.locator("#game")).toContainText("Не удалось запустить игру: Backend недоступен");
  expect(pageErrors).toEqual([]);
});

test("malformed canonical state is surfaced without crashing the page", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.route("**/api/state/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: "{}"
    });
  });

  await page.goto("/");
  await expect(page.locator("#game")).toContainText("Не удалось запустить игру: Некорректный ответ backend");
  expect(pageErrors).toEqual([]);
});
