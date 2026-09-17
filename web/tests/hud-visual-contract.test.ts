import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const mainSource = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
const styles = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

test("normal HUD exposes a stable location-objective-resources hierarchy", () => {
  assert.match(mainSource, /hud\.dataset\.hudLayout = "structured"/);
  assert.match(mainSource, /className = "hud-location"/);
  assert.match(mainSource, /className = "hud-objective"/);
  assert.match(mainSource, /className = "hud-resources"/);
  assert.match(mainSource, /className = "hud-resource hud-resource-coins"/);
  assert.match(mainSource, /hud\.replaceChildren\(location, objectiveText, resources\)/);
});

test("HUD styling keeps the objective flexible and mobile layout bounded", () => {
  assert.match(styles, /#hud\s*\{[\s\S]*grid-template-columns:\s*auto minmax\(0, 1fr\) auto;/);
  assert.match(styles, /\.hud-objective\s*\{[\s\S]*min-width:\s*0;/);
  assert.match(styles, /@media \(max-width: 700px\)[\s\S]*#hud\s*\{[\s\S]*grid-template-columns:\s*minmax\(0, 1fr\) auto;/);
  assert.match(styles, /@media \(max-width: 700px\)[\s\S]*\.hud-objective\s*\{[\s\S]*grid-column:\s*1 \/ -1;/);
  assert.match(styles, /\.hud-location\s*\{[\s\S]*border-left:\s*4px solid #65d5d9;/);
  assert.match(styles, /\.hud-resource-coins\s*\{[\s\S]*color:\s*#e7b35c;/);
});
