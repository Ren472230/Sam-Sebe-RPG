import { expect, test } from "@playwright/test";

test("desktop interaction ribbon renders the live neutral action surface clearly", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 820 });
  await page.goto("/");

  const hint = page.locator("#interaction-hint");
  await expect(hint).toBeVisible();
  await expect(hint).toHaveAttribute("role", "status");
  await expect(hint).toHaveAttribute("aria-live", "polite");
  await expect(hint).toHaveAttribute("aria-atomic", "true");
  await expect(hint).toHaveAttribute("data-contextual", "false");
  await expect(hint).toHaveAttribute("aria-label", "Подсказка управления");

  const presentation = await hint.evaluate((element) => ({
    label: getComputedStyle(element, "::before").content,
    border: getComputedStyle(element).borderLeftColor,
    minHeight: element.getBoundingClientRect().height
  }));
  expect(presentation.label).toContain("Подсказка");
  expect(presentation.border).toBe("rgb(101, 213, 217)");
  expect(presentation.minHeight).toBeGreaterThanOrEqual(40);
});

test("390px interaction ribbon and touch action stay bounded with durable pressed feedback", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  const hint = page.locator("#interaction-hint");
  const action = page.getByRole("button", { name: "Взаимодействовать", exact: true });
  await expect(hint).toBeVisible();
  await expect(action).toBeVisible();
  await expect(hint).toHaveAttribute("data-contextual", "false");
  await expect(action).toHaveAttribute("data-contextual", "false");
  await expect(action.locator(".touch-action-context")).toHaveText("взаимодействие");

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
  expect(presentation.label).toContain("Подсказка");
  expect(presentation.overflowWrap).toBe("anywhere");

  await action.dispatchEvent("pointerdown", { pointerId: 91, pointerType: "touch", isPrimary: true });
  await expect(action).toHaveAttribute("data-pressed", "true");
  const pressed = await action.evaluate((element) => ({
    background: getComputedStyle(element).backgroundColor,
    borderLeft: getComputedStyle(element).borderLeftColor
  }));
  expect(pressed.background).toBe("rgb(101, 213, 217)");
  expect(pressed.borderLeft).toBe("rgb(225, 59, 63)");
  await page.dispatchEvent("body", "pointerup", { pointerId: 91, pointerType: "touch", isPrimary: true });
  await expect(action).toHaveAttribute("data-pressed", "false");

  await page.screenshot({ path: "test-results/interaction-feedback-mobile-390.png", fullPage: true });
});
