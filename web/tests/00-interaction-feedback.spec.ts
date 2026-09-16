import { expect, test } from "@playwright/test";

async function setContextualHint(page: import("@playwright/test").Page, text: string): Promise<void> {
  await page.locator("#interaction-hint").evaluate((element, nextText) => {
    element.textContent = nextText;
  }, text);
}

test("desktop interaction ribbon exposes a distinct contextual action state", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 820 });
  await page.goto("/");

  const hint = page.locator("#interaction-hint");
  await expect(hint).toHaveAttribute("role", "status");
  await expect(hint).toHaveAttribute("aria-live", "polite");
  await expect(hint).toHaveAttribute("data-contextual", "false");

  await setContextualHint(page, "Действие – поговорить с Ореном");
  await expect(hint).toHaveAttribute("data-contextual", "true");
  await expect(hint).toHaveAttribute("aria-label", "Доступно действие: поговорить с Ореном");

  const presentation = await hint.evaluate((element) => ({
    label: getComputedStyle(element, "::before").content,
    border: getComputedStyle(element).borderLeftColor
  }));
  expect(presentation.label).toContain("Действие");
  expect(presentation.border).toBe("rgb(225, 59, 63)");
});

test("390px interaction ribbon and touch action share context without horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  const hint = page.locator("#interaction-hint");
  const action = page.getByRole("button", { name: "Взаимодействовать", exact: true });
  await expect(action).toBeVisible();
  await expect(action).toHaveAttribute("data-contextual", "false");
  await expect(action.locator(".touch-action-context")).toHaveText("взаимодействие");

  await setContextualHint(page, "Действие – подобрать дрова");
  await expect(hint).toHaveAttribute("data-contextual", "true");
  await expect(action).toHaveAttribute("data-contextual", "true");
  await expect(action.locator(".touch-action-context")).toHaveText("подобрать дрова");
  await expect(action).toHaveAttribute("aria-label", "Взаимодействовать");

  const layout = await page.evaluate(() => ({
    viewportWidth: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.scrollWidth
  }));
  expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewportWidth);
  expect(layout.bodyWidth).toBeLessThanOrEqual(layout.viewportWidth);

  const presentation = await hint.evaluate((element) => ({
    label: getComputedStyle(element, "::before").content,
    overflowWrap: getComputedStyle(element).overflowWrap
  }));
  expect(presentation.label).toContain("Действие");
  expect(presentation.overflowWrap).toBe("anywhere");

  await page.screenshot({ path: "test-results/interaction-feedback-mobile-390.png", fullPage: true });
});
