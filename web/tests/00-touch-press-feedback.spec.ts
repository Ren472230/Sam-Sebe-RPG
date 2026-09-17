import { expect, test } from "@playwright/test";

test("390px touch controls keep visible held feedback and release it cleanly", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.locator("#hud")).toContainText("Цель:");

  const right = page.getByRole("button", { name: "Вправо", exact: true });
  await expect(right).toBeVisible();
  await expect(right).toHaveAttribute("data-pressed", "false");

  const before = Number(await page.locator("body").getAttribute("data-player-x"));
  await right.dispatchEvent("pointerdown", {
    pointerId: 41,
    pointerType: "touch",
    isPrimary: true
  });

  await expect(right).toHaveAttribute("data-pressed", "true");
  const pressedStyle = await right.evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      backgroundColor: style.backgroundColor,
      boxShadow: style.boxShadow,
      transform: style.transform
    };
  });
  expect(pressedStyle.backgroundColor).toBe("rgb(101, 213, 217)");
  expect(pressedStyle.boxShadow).not.toBe("none");
  expect(pressedStyle.transform).not.toBe("none");

  await page.waitForTimeout(180);
  await right.dispatchEvent("pointerup", {
    pointerId: 41,
    pointerType: "touch",
    isPrimary: true
  });
  await expect(right).toHaveAttribute("data-pressed", "false");
  await expect.poll(async () => Number(await page.locator("body").getAttribute("data-player-x"))).toBeGreaterThan(before);

  await right.dispatchEvent("pointerdown", {
    pointerId: 42,
    pointerType: "touch",
    isPrimary: true
  });
  await expect(right).toHaveAttribute("data-pressed", "true");
  await page.evaluate(() => window.dispatchEvent(new Event("blur")));
  await expect(right).toHaveAttribute("data-pressed", "false");
});
