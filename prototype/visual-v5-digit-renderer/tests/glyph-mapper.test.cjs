const test = require('node:test');
const assert = require('node:assert/strict');
const mapper = require('../glyph-mapper.js');

test('chooseGlyph deterministically selects the closest profile', () => {
  const sample = { luminance: 0.8, gradientX: 0, gradientY: 0, patch: [1,1,1,1] };
  const profiles = {
    '1': { density: 0.2, edgeX: 0, edgeY: 0, patch: [0,0,0,0] },
    '8': { density: 0.8, edgeX: 0, edgeY: 0, patch: [1,1,1,1] },
  };
  assert.equal(mapper.chooseGlyph(sample, profiles, null, mapper.DEFAULT_WEIGHTS), '8');
  assert.equal(mapper.chooseGlyph(sample, profiles, null, mapper.DEFAULT_WEIGHTS), '8');
});

test('minimum foreground brightness lifts dark source colors without adding a background block', () => {
  const rgb = mapper.correctForegroundColor([8, 10, 12], {
    saturation: 1,
    contrast: 1,
    gamma: 1,
    minBrightness: 0.2,
  });
  assert.ok(Math.max(...rgb) >= 50);
});

test('canonical order resolves exact score ties deterministically', () => {
  const sample = { luminance: 0.5, gradientX: 0, gradientY: 0, patch: [0.5] };
  const same = { density: 0.5, edgeX: 0, edgeY: 0, patch: [0.5] };
  assert.equal(mapper.chooseGlyph(sample, { '8': same, '2': same }, null, mapper.DEFAULT_WEIGHTS), '2');
});

test('mapSamples applies one explicit marker after normal mapping', () => {
  const profiles = {
    '0': { density: 0.5, edgeX: 0, edgeY: 0, patch: [0.5] },
  };
  const samples = Array.from({ length: 6 }, (_, i) => ({
    x: i % 3,
    y: Math.floor(i / 3),
    rgb: [100,120,140],
    luminance: 0.5,
    gradientX: 0,
    gradientY: 0,
    patch: [0.5],
  }));
  const cells = mapper.mapSamples(samples, profiles, {
    columns: 3,
    rows: 2,
    marker: { normalizedX: 1, normalizedY: 1, glyph: '@', color: [255,240,170] },
  });
  assert.equal(cells.filter((c) => c.glyph === '@').length, 1);
  assert.equal(cells[5].glyph, '@');
  assert.deepEqual(cells[5].color, [255,240,170]);
});

test('scoreGlyph continuity is a weak tie-breaker, not a shape override', () => {
  const sample = { luminance: 0.7, gradientX: 0, gradientY: 0, patch: [1,1] };
  const close = { density: 0.7, edgeX: 0, edgeY: 0, patch: [1,1] };
  const bad = { density: 0.1, edgeX: 1, edgeY: 1, patch: [0,0] };
  assert.ok(mapper.scoreGlyph(sample, close, '1', mapper.DEFAULT_WEIGHTS, '8') < mapper.scoreGlyph(sample, bad, '1', mapper.DEFAULT_WEIGHTS, '1'));
});
