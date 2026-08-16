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
    variance: 0.2,
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

test('flat near-tied regions use deterministic glyph diversity instead of one repeated glyph', () => {
  const profiles = {
    '0': { density: 0.80, edgeX: 0, edgeY: 0, patch: [1,1,1,1] },
    '8': { density: 0.77, edgeX: 0, edgeY: 0, patch: [0.98,0.98,0.98,0.98] },
    '3': { density: 0.74, edgeX: 0, edgeY: 0, patch: [0.95,0.95,0.95,0.95] },
  };
  const samples = Array.from({ length: 24 }, (_, i) => ({
    x: i % 8,
    y: Math.floor(i / 8),
    rgb: [130,190,220],
    luminance: 0.80,
    variance: 0.002,
    gradientX: 0.002,
    gradientY: 0.001,
    patch: [1,1,1,1],
  }));

  const first = mapper.mapSamples(samples, profiles, { columns: 8, rows: 3 });
  const second = mapper.mapSamples(samples, profiles, { columns: 8, rows: 3 });
  const firstGlyphs = first.map((cell) => cell.glyph);
  const secondGlyphs = second.map((cell) => cell.glyph);

  assert.deepEqual(firstGlyphs, secondGlyphs);
  assert.ok(new Set(firstGlyphs).size > 1, 'flat region should not collapse to a single repeated glyph');
});

test('structured high-variance cells keep strict best-match glyph selection', () => {
  const profiles = {
    '0': { density: 0.80, edgeX: 0.30, edgeY: 0.10, patch: [1,1,1,1] },
    '8': { density: 0.77, edgeX: 0.28, edgeY: 0.10, patch: [0.98,0.98,0.98,0.98] },
  };
  const samples = Array.from({ length: 6 }, (_, i) => ({
    x: i,
    y: 0,
    rgb: [160,120,80],
    luminance: 0.80,
    variance: 0.20,
    gradientX: 0.30,
    gradientY: 0.10,
    patch: [1,1,1,1],
  }));

  const cells = mapper.mapSamples(samples, profiles, { columns: 6, rows: 1 });
  assert.deepEqual(cells.map((cell) => cell.glyph), ['0','0','0','0','0','0']);
});
