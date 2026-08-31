import { expect, test } from "@playwright/test";

test("world pulse turns waiting into a visible world change", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto("/");

  const pulse = page.locator("#world-pulse");
  await expect(pulse).toBeVisible();
  await expect(pulse.getByRole("heading", { name: "Живой мир" })).toBeVisible();
  await expect(pulse).toContainText("Шаг 0");
  await expect(pulse).toContainText("Рядом: Мира");

  await pulse.getByRole("button", { name: "Подождать 5 шагов" }).click();

  await expect(pulse).toContainText("Шаг 5");
  await expect(pulse).toContainText("Мира просит древесину");
  await expect(pulse).toContainText("Каспар подобрал древесину");
  await page.screenshot({ path: "test-results/00-world-pulse.png", fullPage: true });
});
