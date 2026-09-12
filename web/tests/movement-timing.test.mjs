import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

const require = createRequire(import.meta.url);
const TimeStep = require("phaser/src/core/TimeStep.js");

// Execute the actual scene update/collision code and Phaser clock without a GPU.
// Only browser/rendering dependencies are replaced; no movement is reimplemented.
function sceneHarness(name) {
  class Element {}
  const dialogue = { hidden: true };
  const document = { body: { dataset: {} }, activeElement: null,
    getElementById: () => dialogue };
  const window = { performance, matchMedia: () => ({ matches: false }) };
  const scope = { window, document, HTMLInputElement: Element,
    HTMLTextAreaElement: Element, HTMLElement: Element };
  const modules = {
    phaser: { Scene: class {}, Math: { Clamp: (n, min, max) => Math.min(max, Math.max(min, n)) } },
    "../api": {},
    "../productionArt": {},
    "../runtime": { getRuntime: () => ({ state: { snapshot: { world: { visible_actors: [] } } } }) }
  };
  function load(relativePath) {
    const source = readFileSync(new URL(relativePath, import.meta.url), "utf8");
    const { outputText } = ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true }
    });
    const exports = {};
    runInNewContext(outputText, { ...scope, exports, require: (id) => {
      if (!(id in modules)) throw new Error(`Unexpected scene dependency: ${id}`);
      return modules[id];
    } });
    return exports;
  }
  modules["../controlHints"] = load("../src/controlHints.ts");
  const Scene = load(`../src/scenes/${name}.ts`)[name];
  const scene = new Scene();
  scene.player = { x: 330, y: 455 };
  scene.keys = Object.fromEntries(["A", "D", "W", "S"].map(key => [key, { isDown: false }]));
  scene.hint = { textContent: "" };
  scene.time = { now: 0 };

  // Read the shipped Phaser configuration, including its default when fps is absent.
  const main = ts.createSourceFile("main.ts",
    readFileSync(new URL("../src/main.ts", import.meta.url), "utf8"), ts.ScriptTarget.Latest, true);
  let config;
  function visit(node) {
    if (ts.isNewExpression(node) && node.expression.getText(main) === "Phaser.Game") {
      config = runInNewContext(`(${node.arguments[0].getText(main)})`, { Phaser: { AUTO: 0 }, initialScenes: [] });
    }
    ts.forEachChild(node, visit);
  }
  visit(main);
  assert.ok(config, "The game must instantiate its Phaser configuration");
  globalThis.window = window;
  const clock = new TimeStep({}, config.fps ?? {});
  clock.deltaHistory = Array(clock.deltaSmoothingMax).fill(1000 / clock.targetFps);
  clock.resetDelta();
  clock.lastTime = 0;
  clock.callback = (time, delta) => { scene.time.now = time; scene.update(time, delta); };
  let now = 0;
  return { scene, dialogue, frame(ms) { now += ms; clock.step(now); } };
}

for (const name of ["VillageScene", "TavernScene"]) {
  test(`${name}: walking speed survives ten frames per second`, () => {
    function walk(frames, frameMs) {
      const game = sceneHarness(name);
      game.scene.keys.D.isDown = true;
      for (let i = 0; i < frames; i++) game.frame(frameMs);
      return game.scene.player.x - 330;
    }
    const normal = walk(60, 1000 / 60);
    const slow = walk(10, 100);
    assert.ok(Math.abs(normal - 220) < 1, `Normal one-second walk: ${normal}`);
    assert.ok(Math.abs(slow - normal) < 1, `Slow walk ${slow}; normal walk ${normal}`);
  });

  test(`${name}: a suspended frame cannot cause a long teleport`, () => {
    const game = sceneHarness(name);
    game.scene.keys.D.isDown = true;
    game.frame(5000);
    const displacement = game.scene.player.x - 330;
    assert.ok(displacement >= 0 && displacement <= 55, `Resumed displacement: ${displacement}`);
  });

  test(`${name}: dialogue blocks held movement and carries no movement debt`, () => {
    const game = sceneHarness(name);
    game.scene.keys.D.isDown = true;
    game.dialogue.hidden = false;
    game.frame(2000);
    assert.equal(game.scene.player.x, 330);
    game.dialogue.hidden = true;
    game.frame(1000 / 60);
    assert.ok(game.scene.player.x - 330 < 4);
  });
}

test("VillageScene: a long frame keeps the player outside the well", () => {
  const game = sceneHarness("VillageScene");
  game.scene.player.x = 500;
  game.scene.keys.W.isDown = true;
  game.frame(5000);
  assert.ok(game.scene.player.y >= 441, `Player crossed the well: y=${game.scene.player.y}`);
  assert.ok(game.scene.player.y < 455, "Player can approach the obstacle");
});
