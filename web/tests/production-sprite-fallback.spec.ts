import { expect, test } from "@playwright/test";

const productionLayer = "village/L3_ARCHITECTURE_PARTIAL.webp";

test("ready production scene keeps prototype sprites when production sprite slots are absent", async ({ page }) => {
  await page.route("**/assets/production/manifest.json", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        version: 2,
        status: "partial",
        canvas: { width: 960, height: 540 },
        village: {
          layers: {
            sky: productionLayer,
            distant_nature: productionLayer,
            mid_nature: productionLayer,
            architecture: productionLayer,
            gameplay: productionLayer,
            foreground: ""
          },
          parallax: { enabled: false }
        },
        tavern: { layers: {} },
        characters: { player: "", oren: "" },
        props: { firewood: "" }
      })
    });
  });

  await page.goto("/");

  await expect.poll(() => page.locator("body").getAttribute("data-village-art")).toBe("production");
  await expect.poll(() => page.locator("body").getAttribute("data-player-art")).toBe("prototype");
  await expect.poll(() => page.locator("body").getAttribute("data-firewood-art")).toBe("prototype");
});
