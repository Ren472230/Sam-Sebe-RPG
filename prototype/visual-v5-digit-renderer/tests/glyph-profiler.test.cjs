const test = require('node:test');
const assert = require('node:assert/strict');
const profiler = require('../glyph-profiler.js');

test('analyzeMask distinguishes empty and dense masks', () => {
  const empty = profiler.analyzeMask(new Float32Array(16), 4, 4);
  const dense = profiler.analyzeMask(new Float32Array(16).fill(1), 4, 4);
  assert.equal(empty.density, 0);
  assert.equal(dense.density, 1);
});

test('allowed glyph set contains only the approved characters', () => {
  assert.deepEqual(profiler.ALLOWED_GLYPHS, ['0','1','2','3','4','5','6','7','8','9','.',':','-']);
});

test('analyzeMask captures center of mass and directional edges', () => {
  const mask = new Float32Array([
    0,0,1,1,
    0,0,1,1,
    0,0,1,1,
    0,0,1,1,
  ]);
  const f = profiler.analyzeMask(mask, 4, 4);
  assert.ok(f.centerX > 0.6);
  assert.ok(f.edgeX > f.edgeY);
  assert.equal(f.patch.length, 24);
});

test('analyzeMask clamps input values into normalized range', () => {
  const f = profiler.analyzeMask(new Float32Array([-1, 2, 0.5, 1]), 2, 2);
  assert.ok(f.density >= 0 && f.density <= 1);
  assert.ok(f.patch.every((v) => v >= 0 && v <= 1));
});
