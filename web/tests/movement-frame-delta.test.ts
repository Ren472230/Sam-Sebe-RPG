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


test("held movement uses wall-clock hold time when Phaser loop duration is smoothed", () => {
  const key = { isDown: true, timeDown: 100, timeUp: 0, duration: 0, getDuration: () => 16 };

  assert.equal(effectiveHeldDelta(16, key, 900), MAX_MOVEMENT_CATCHUP_MS);
});


test("held movement drains catch-up through collision-safe substeps", () => {
  const key = { isDown: true, timeDown: 100, timeUp: 0, duration: 0, getDuration: () => 16 };
  const steps: number[] = [];

  applyMovementDelta(effectiveHeldDelta(16, key, 900), (distance) => steps.push(distance));

  assert.equal(steps.reduce((total, distance) => total + distance, 0), MAX_MOVEMENT_CATCHUP_MS * 0.22);
  assert.ok(steps.every((distance) => distance <= 11));
});


test("a key pulse completed entirely between render frames is preserved", () => {
  const key = { isDown: false, timeDown: 100, timeUp: 180, duration: 80, getDuration: () => 80 };

  assert.equal(effectiveHeldDelta(16, key, 900), 80);
  assert.equal(effectiveHeldDelta(16, key, 916), 0);
});


test("a release applies only the unconsumed remainder of the same physical press", () => {
  const key = { isDown: true, timeDown: 100, timeUp: 0, duration: 0, getDuration: () => 40 };

  assert.equal(effectiveHeldDelta(16, key, 140), 40);
  key.isDown = false;
  key.timeUp = 180;
  key.duration = 80;
  assert.equal(effectiveHeldDelta(16, key, 200), 40);
  assert.equal(effectiveHeldDelta(16, key, 216), 0);
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


test("a new physical press clears leftover catch-up from the previous hold", () => {
  const key = { isDown: true, timeDown: 100, timeUp: 0, duration: 0, getDuration: () => 16 };

  assert.equal(effectiveHeldDelta(16, key, 900), MAX_MOVEMENT_CATCHUP_MS);
  key.timeDown = 1000;
  assert.equal(effectiveHeldDelta(800, key, 1025), 25);
});


test("held movement falls back to Phaser duration when DOM and performance clocks are incomparable", () => {
  const key = { isDown: true, timeDown: 1_700_000_000_000, timeUp: 0, duration: 0, getDuration: () => 37 };

  assert.equal(effectiveHeldDelta(16, key, 900), 37);
});
