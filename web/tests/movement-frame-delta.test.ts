import assert from "node:assert/strict";
import test from "node:test";

import { applyMovementDelta, effectiveHeldDelta } from "../src/movement.ts";


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
  const key = { isDown: true, timeDown: 100, getDuration: () => 16 };

  assert.equal(effectiveHeldDelta(16, key, 900), 200);
  assert.equal(effectiveHeldDelta(16, key, 916), 200);
  assert.equal(effectiveHeldDelta(16, key, 932), 200);
  assert.equal(effectiveHeldDelta(16, key, 948), 200);
});


test("held movement drains a wall-clock stall through collision-safe substeps", () => {
  const key = { isDown: true, timeDown: 100, getDuration: () => 16 };
  const steps: number[] = [];

  applyMovementDelta(effectiveHeldDelta(16, key, 900), (distance) => steps.push(distance));

  assert.deepEqual(steps, [11, 11, 11, 11]);
  assert.equal(steps.reduce((total, distance) => total + distance, 0), 44);
});


test("a short new press after a stall is charged only for its real hold duration", () => {
  const key = { isDown: true, timeDown: 820, getDuration: () => 16 };

  assert.equal(effectiveHeldDelta(800, key, 900), 80);
});


test("a new physical press clears leftover catch-up from the previous hold", () => {
  const key = { isDown: true, timeDown: 100, getDuration: () => 16 };

  assert.equal(effectiveHeldDelta(16, key, 900), 200);
  key.timeDown = 1000;
  assert.equal(effectiveHeldDelta(800, key, 1025), 25);
});


test("held movement falls back to Phaser duration when DOM and performance clocks are incomparable", () => {
  const key = { isDown: true, timeDown: 1_700_000_000_000, getDuration: () => 37 };

  assert.equal(effectiveHeldDelta(16, key, 900), 37);
});
