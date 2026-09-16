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


test("held movement amortizes a continuous render stall instead of discarding or applying it in one jump", () => {
  let heldMs = 900;
  const key = { isDown: true, timeDown: 100, getDuration: () => heldMs };

  assert.equal(effectiveHeldDelta(800, key), 200);
  heldMs = 916;
  assert.equal(effectiveHeldDelta(16, key), 200);
  heldMs = 932;
  assert.equal(effectiveHeldDelta(16, key), 200);
  heldMs = 948;
  assert.equal(effectiveHeldDelta(16, key), 200);
});


test("held movement recovers elapsed hold time when Phaser smooths a stalled frame delta", () => {
  let heldMs = 16;
  const key = { isDown: true, timeDown: 150, getDuration: () => heldMs };

  assert.equal(effectiveHeldDelta(16, key), 16);

  heldMs = 816;
  assert.equal(effectiveHeldDelta(16, key), 200);
  heldMs = 832;
  assert.equal(effectiveHeldDelta(16, key), 200);
  heldMs = 848;
  assert.equal(effectiveHeldDelta(16, key), 200);
  heldMs = 864;
  assert.equal(effectiveHeldDelta(16, key), 200);
  heldMs = 880;
  assert.equal(effectiveHeldDelta(16, key), 64);
});


test("a short new press after a stall is charged only for its observed hold duration", () => {
  const key = { isDown: true, timeDown: 200, getDuration: () => 80 };

  assert.equal(effectiveHeldDelta(800, key), 80);
});


test("a new physical press clears leftover catch-up from the previous hold", () => {
  let heldMs = 900;
  const key = { isDown: true, timeDown: 300, getDuration: () => heldMs };

  assert.equal(effectiveHeldDelta(800, key), 200);
  key.timeDown = 400;
  heldMs = 25;
  assert.equal(effectiveHeldDelta(800, key), 25);
});
