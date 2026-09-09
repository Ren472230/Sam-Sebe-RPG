import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  VILLAGE_PARALLAX_COEFFICIENTS,
  getProductionReadiness,
  normalizeProductionManifest,
  parallaxOffset
} from "../src/productionManifest.ts";

const villageCore = {
  sky: "village/L0_SKY.webp",
  distant_nature: "village/L1_DISTANT_NATURE.webp",
  mid_nature: "village/L2_MID_NATURE.webp",
  architecture: "village/L3_ARCHITECTURE.webp",
  gameplay: "village/L4_GAMEPLAY.webp"
};

test("v2 village readiness is independent from tavern and optional gameplay sprites", () => {
  const manifest = normalizeProductionManifest({
    version: 2,
    status: "partial",
    canvas: { width: 960, height: 540 },
    village: { layers: villageCore, parallax: { enabled: false } },
    tavern: { layers: {} },
    characters: {},
    props: {}
  });

  const readiness = getProductionReadiness(manifest);
  assert.equal(readiness.village.ready, true);
  assert.equal(readiness.tavern.ready, false);
  assert.equal(readiness.player, false);
  assert.equal(readiness.oren, false);
  assert.equal(readiness.firewood, false);
});

test("v2 village missing one core layer falls back truthfully and reports the missing slot", () => {
  const manifest = normalizeProductionManifest({
    version: 2,
    status: "partial",
    canvas: { width: 960, height: 540 },
    village: {
      layers: { ...villageCore, architecture: "" },
      parallax: { enabled: false }
    },
    tavern: { layers: {} },
    characters: {},
    props: {}
  });

  const readiness = getProductionReadiness(manifest);
  assert.equal(readiness.village.ready, false);
  assert.equal(readiness.village.partial, true);
  assert.ok(readiness.village.present > 0);
  assert.deepEqual(readiness.village.missing, ["village.layers.architecture"]);
});

test("v2 reports exact partial Village layers without coupling them to absent core slots", () => {
  const manifest = normalizeProductionManifest({
    version: 2,
    status: "partial",
    canvas: { width: 960, height: 540 },
    village: {
      layers: { architecture: "village/L3.png", gameplay: "village/L4.png" },
      parallax: { enabled: false }
    },
    tavern: { layers: {} },
    characters: {},
    props: {}
  });

  const readiness = getProductionReadiness(manifest);
  assert.equal(readiness.village.ready, false);
  assert.equal(readiness.village.partial, true);
  assert.deepEqual(readiness.village.available, ["architecture", "gameplay"]);
  assert.deepEqual(readiness.village.missing, [
    "village.layers.sky",
    "village.layers.distant_nature",
    "village.layers.mid_nature"
  ]);
});

test("checked-in stream manifest activates the complete temporary SVG pack", () => {
  const raw = JSON.parse(readFileSync(new URL("../public/assets/production/manifest.json", import.meta.url), "utf8"));
  const manifest = normalizeProductionManifest(raw);
  const readiness = getProductionReadiness(manifest);

  assert.equal(manifest.status, "ready");
  assert.equal(manifest.village.layers.sky, "village/sky.svg");
  assert.equal(manifest.village.layers.distant_nature, "village/distant_nature.svg");
  assert.equal(manifest.village.layers.mid_nature, "village/mid_nature.svg");
  assert.equal(manifest.village.layers.architecture, "village/architecture.svg");
  assert.equal(manifest.village.layers.gameplay, "village/gameplay.svg");
  assert.equal(manifest.village.layers.foreground, "village/foreground.svg");
  assert.equal(manifest.village.parallax.enabled, false);
  assert.equal(readiness.village.ready, true);
  assert.equal(manifest.tavern.layers.background, "tavern/background.svg");
  assert.equal(manifest.tavern.layers.foreground, "tavern/foreground.svg");
  assert.equal(readiness.tavern.ready, true);
  assert.equal(manifest.characters.player, "characters/player.svg");
  assert.equal(manifest.characters.oren, "characters/oren.svg");
  assert.equal(manifest.props.firewood, "props/firewood.svg");
});

test("ready production scenes take precedence over prototype fallback and SVG assets use the SVG loader", () => {
  const source = readFileSync(new URL("../src/productionArt.ts", import.meta.url), "utf8");

  assert.match(
    source,
    /if \(!currentReadiness\.village\.ready && renderVillagePrototypeBackground\(scene\)\) return true;/
  );
  assert.match(
    source,
    /if \(!currentReadiness\.tavern\.ready && renderTavernPrototypeBackground\(scene\)\) return true;/
  );
  assert.match(source, /path\.toLowerCase\(\)\.endsWith\("\.svg"\)/);
  assert.match(source, /scene\.load\.svg\(key, assetUrl\(path\)\)/);
});

test("legacy v1 awaiting_assets paths remain disabled so placeholder paths are never fetched", () => {
  const manifest = normalizeProductionManifest({
    version: 1,
    status: "awaiting_assets",
    canvas: { width: 960, height: 540 },
    village: { layers: { sky: "village/sky.webp", far_world: "village/far.webp", mid_world: "village/mid.webp" } },
    tavern: { layers: { background: "tavern/background.webp" } },
    characters: { player: "characters/player.webp", oren: "characters/oren.webp" },
    props: { firewood: "props/firewood.webp" }
  });

  const readiness = getProductionReadiness(manifest);
  assert.equal(readiness.village.present, 0);
  assert.equal(readiness.village.partial, false);
  assert.equal(readiness.tavern.ready, false);
  assert.equal(readiness.player, false);
  assert.equal(readiness.oren, false);
  assert.equal(readiness.firewood, false);
});

test("legacy v1 ready remains backward compatible without coupling village to tavern", () => {
  const manifest = normalizeProductionManifest({
    version: 1,
    status: "ready",
    canvas: { width: 960, height: 540 },
    village: { layers: { sky: "village/sky.webp", far_world: "village/far.webp", mid_world: "village/mid.webp" } },
    tavern: { layers: { background: "" } },
    characters: { player: "", oren: "" },
    props: { firewood: "" }
  });

  const readiness = getProductionReadiness(manifest);
  assert.equal(readiness.village.ready, true);
  assert.equal(readiness.village.partial, false);
  assert.equal(readiness.tavern.ready, false);
});

test("historical parallax coefficients are exact and offsets depend only on camera travel", () => {
  assert.deepEqual(VILLAGE_PARALLAX_COEFFICIENTS, {
    sky: 0.005,
    distant_nature: 0.045,
    mid_nature: 0.16,
    architecture: 0.43,
    gameplay: 1,
    foreground: 1.4
  });
  assert.equal(parallaxOffset("sky", 100), -0.5);
  assert.equal(parallaxOffset("architecture", 100), -43);
  assert.equal(parallaxOffset("gameplay", 100), -100);
  assert.equal(parallaxOffset("foreground", 100), -140);
  assert.equal(parallaxOffset("foreground", 0), 0);
});

test("malformed manifest becomes a safe empty fallback instead of throwing", () => {
  const manifest = normalizeProductionManifest({ version: 2, canvas: { width: 1, height: 2 } });
  const readiness = getProductionReadiness(manifest);
  assert.equal(manifest.status, "awaiting_assets");
  assert.equal(readiness.village.ready, false);
  assert.equal(readiness.village.partial, false);
  assert.equal(readiness.village.present, 0);
});
