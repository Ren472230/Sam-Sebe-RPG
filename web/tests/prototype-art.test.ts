import assert from "node:assert/strict";
import { readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  PROTOTYPE_ASSETS,
  getPrototypeReadiness,
  prototypeAssetUrl
} from "../src/prototypeManifest.ts";

test("prototype manifest stays isolated from production art paths", () => {
  assert.deepEqual(PROTOTYPE_ASSETS, {
    villageBackground: "prototype/village.svg",
    tavernBackground: "prototype/tavern.svg",
    player: "prototype/player.svg",
    oren: "prototype/oren.svg",
    firewood: "prototype/firewood.svg"
  });
  assert.equal(prototypeAssetUrl(PROTOTYPE_ASSETS.villageBackground), "/assets/prototype/village.svg");
});

test("prototype readiness is scene-specific and all-or-nothing", () => {
  const all = new Set(["villageBackground", "tavernBackground", "player", "oren", "firewood"] as const);
  assert.deepEqual(getPrototypeReadiness(all), { village: true, tavern: true });

  const missingFirewood = new Set(["villageBackground", "tavernBackground", "player", "oren"] as const);
  assert.deepEqual(getPrototypeReadiness(missingFirewood), { village: false, tavern: true });

  const missingOren = new Set(["villageBackground", "tavernBackground", "player", "firewood"] as const);
  assert.deepEqual(getPrototypeReadiness(missingOren), { village: true, tavern: false });
});

test("checked-in prototype art is complete and non-trivial", () => {
  for (const path of Object.values(PROTOTYPE_ASSETS)) {
    const filePath = fileURLToPath(new URL(`../public/assets/${path}`, import.meta.url));
    assert.ok(statSync(filePath).size > 500, `${path} must contain real artwork`);
    assert.match(readFileSync(filePath, "utf8"), /<svg\b/);
  }

  const provenance = JSON.parse(readFileSync(new URL("../public/assets/prototype/provenance.json", import.meta.url), "utf8"));
  assert.equal(provenance.mode, "prototype");
  assert.equal(provenance.production_canon_replaced, false);
  assert.deepEqual(provenance.external_assets, []);
});

test("runtime bridge gives complete prototype art precedence without deleting existing fallbacks", () => {
  const source = readFileSync(new URL("../src/productionArt.ts", import.meta.url), "utf8");
  const prototypeRuntime = readFileSync(new URL("../src/prototypeArt.ts", import.meta.url), "utf8");
  assert.match(source, /preloadVillagePrototypeArt\(scene\)/);
  assert.match(source, /preloadTavernPrototypeArt\(scene\)/);
  assert.match(source, /if \(renderVillagePrototypeBackground\(scene\)\) return true;/);
  assert.match(source, /if \(renderTavernPrototypeBackground\(scene\)\) return true;/);
  assert.match(source, /document\.body\.dataset\.villageArt === "prototype"/);
  assert.match(source, /document\.body\.dataset\.tavernArt === "prototype"/);
  assert.match(prototypeRuntime, /scene\.load\.svg\(key, prototypeAssetUrl\(path\)\)/);
});
