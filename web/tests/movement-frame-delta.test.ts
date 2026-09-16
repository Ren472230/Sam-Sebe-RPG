import assert from "node:assert/strict";
import test from "node:test";

import { MAX_MOVEMENT_CATCHUP_MS, applyMovementDelta, effectiveHeldDelta } from "../src/movement.ts";


test("movement delta preserves elapsed distance while splitting long frames", () => {
  const steps: number[] = [];

  applyMovementDelta(125, (distance) => steps.push(distance));

  assert.deepEqual(steps, [11, 11, 5.5]);
  assert.equal(steps.reduce((total, distance) => total + distance, 0), 27.5);
});


test("movement delta keeps normal-frame gameplay speed unchanged", () => {
  const steps: number[] = [];

  applyMovementDelta(16, (distance) => steps.push(distance));

  assert.deepEqual(steps, [3.52]);
});


test("movement delta ignores invalid or non-positive frame durations", () => {
  const steps: number[] = [];

  applyMovementDelta(0, (distance) => steps.push(distance));
  applyMovementDelta(-1, (distance) => steps.push(distance));
  applyMovementDelta(Number.NaN, (distance) => steps.push(distance));

  assert.deepEqual(steps, []);
});


test("a held key never expands one rendered frame into a wall-clock catch-up burst", () => {
  const key = { isDown: true, timeDown: 100, timeUp: 0, duration: 0, getDuration: () => 800 };

  assert.equal(effectiveHeldDelta(16, key, 900), 16);
});


test("live held movement keeps normal frame speed and collision-safe substeps", () => {
  const key = { isDown: true, timeDown: 100, timeUp: 0, duration: 0, getDuration: () => 125 };
  const steps: number[] = [];

  applyMovementDelta(effectiveHeldDelta(125, key, 225), (distance) => steps.push(distance));

  assert.equal(steps.reduce((total, distance) => total + distance, 0), 125 * 0.22);
  assert.ok(steps.every((distance) => distance <= 11));
});


test("a key pulse completed entirely between render frames is preserved", () => {
  const key = { isDown: false, timeDown: 100, timeUp: 180, duration: 80, getDuration: () => 0 };

  assert.equal(effectiveHeldDelta(16, key, 900), 80);
  assert.equal(effectiveHeldDelta(16, key, 916), 0);
});


test("a short tap completes its small release tail after a live frame", () => {
  let currentDuration = 16;
  const key = { isDown: true, timeDown: 100, timeUp: 0, duration: 0, getDuration: () => currentDuration };

  assert.equal(effectiveHeldDelta(16, key, 116), 16);
  key.isDown = false;
  key.timeUp = 180;
  key.duration = 80;
  currentDuration = 0;
  assert.equal(effectiveHeldDelta(16, key, 196), 64);
  assert.equal(effectiveHeldDelta(16, key, 212), 0);
});


test("release after live movement never replays a wall-clock tail", () => {
  let currentDuration = 16;
  const key = { isDown: true, timeDown: 100, timeUp: 0, duration: 0, getDuration: () => currentDuration };

  assert.equal(effectiveHeldDelta(16, key, 116), 16);
  key.isDown = false;
  key.timeUp = 580;
  key.duration = 480;
  currentDuration = 0;
  assert.equal(effectiveHeldDelta(16, key, 600), 0);
  assert.equal(effectiveHeldDelta(16, key, 616), 0);
});


test("a synthetic key-up without a physical key-down never creates movement", () => {
  const key = { isDown: false, timeDown: 0, timeUp: 5_000, duration: 5_000, getDuration: () => 0 };

  assert.equal(effectiveHeldDelta(16, key, 5_100), 0);
});


test("a repeated key-up for an already released press does not replay stale movement", () => {
  const key = { isDown: false, timeDown: 100, timeUp: 180, duration: 80, getDuration: () => 0 };

  assert.equal(effectiveHeldDelta(16, key, 200), 80);
  key.timeUp = 900;
  key.duration = 800;
  assert.equal(effectiveHeldDelta(16, key, 916), 0);
});


test("a new physical press clears consumed time from the previous hold", () => {
  let currentDuration = 800;
  const key = { isDown: true, timeDown: 100, timeUp: 0, duration: 0, getDuration: () => currentDuration };

  assert.equal(effectiveHeldDelta(16, key, 900), 16);
  key.timeDown = 1000;
  currentDuration = 25;
  assert.equal(effectiveHeldDelta(800, key, 1025), 25);
});


test("live movement remains frame-bounded when DOM and Phaser clocks are incomparable", () => {
  const key = { isDown: true, timeDown: 1_700_000_000_000, timeUp: 0, duration: 0, getDuration: () => 37 };

  assert.equal(effectiveHeldDelta(16, key, 900), 16);
});


test("released sparse input still uses bounded catch-up", () => {
  const key = { isDown: false, timeDown: 100, timeUp: 900, duration: 800, getDuration: () => 0 };

  assert.equal(effectiveHeldDelta(16, key, 916), MAX_MOVEMENT_CATCHUP_MS);
  assert.equal(effectiveHeldDelta(16, key, 932), 0);
});
