const test = require('node:test');
const assert = require('node:assert/strict');

const app = require('../app.js');
const mapper = require('../glyph-mapper.js');

test('standalone mapper defaults match the accepted Visual v5 UI color preset', () => {
  assert.deepEqual(mapper.DEFAULT_COLOR, {
    saturation: app.DEFAULTS.saturation,
    contrast: app.DEFAULTS.contrast,
    gamma: app.DEFAULTS.gamma,
    minBrightness: app.DEFAULTS.minBrightness,
  });
});
