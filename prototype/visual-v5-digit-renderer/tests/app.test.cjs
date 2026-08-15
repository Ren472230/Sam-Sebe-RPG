const test = require('node:test');
const assert = require('node:assert/strict');
const { buildSettings, DEFAULTS } = require('../app.js');

test('buildSettings uses 240 columns and approved mapping defaults', () => {
  const settings = buildSettings({ showMarker: true });
  assert.equal(settings.columns, 240);
  assert.deepEqual(settings.weights, { density: 0.40, shape: 0.35, edge: 0.20, continuity: 0.05 });
  assert.deepEqual(settings.color, { saturation: 1.20, contrast: 1.08, gamma: 1.00, minBrightness: 0.16 });
  assert.equal(settings.marker.glyph, '@');
});

test('buildSettings parses form-style strings deterministically', () => {
  const settings = buildSettings({
    columns: '180', zoom: '300', fontSize: '9.5', lineHeight: '10',
    density: '0.5', shape: '0.3', edge: '0.15', continuity: '0.05',
    saturation: '1.4', contrast: '1.1', gamma: '0.9', minBrightness: '0.2',
    showMarker: false, showSource: true,
  });
  assert.equal(settings.columns, 180);
  assert.equal(settings.zoom, 3);
  assert.equal(settings.font.fontSize, 9.5);
  assert.equal(settings.marker, null);
  assert.equal(settings.showSource, true);
});

test('default font remains dependency-free browser native stack', () => {
  assert.match(DEFAULTS.fontFamily, /monospace/);
});
