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


test("held movement charges only observable key time and bounds unrendered catch-up", () => {
  const justPressed = { isDown: true, getDuration: () => 25 };
  const normallyHeld = { isDown: true, getDuration: () => 500 };
  const stalledFrame = { isDown: true, getDuration: () => 900 };
  const released = { isDown: false, getDuration: () => 500 };

  assert.equal(effectiveHeldDelta(125, justPressed), 25);
  assert.equal(effectiveHeldDelta(125, normallyHeld), 125);
  assert.equal(effectiveHeldDelta(800, stalledFrame), 200);
  assert.equal(effectiveHeldDelta(125, released), 0);
});
