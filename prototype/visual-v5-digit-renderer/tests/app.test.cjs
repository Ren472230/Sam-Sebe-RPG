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

test('resolveBenchmarkUrl uses explicit browser-QA source without changing the bundled default', () => {
  const { resolveBenchmarkUrl } = require('../app.js');
  assert.equal(resolveBenchmarkUrl(), 'assets/benchmark-day.png');
  assert.equal(resolveBenchmarkUrl({ benchmarkUrl: 'blob:qa-source' }), 'blob:qa-source');
});

test('computeFitZoom scales a wide glyph surface to the available mobile width', () => {
  const { computeFitZoom } = require('../app.js');
  const zoom = computeFitZoom({ availableWidth: 322, outputWidth: 1155 });
  assert.ok(Math.abs(zoom - (322 / 1155)) < 1e-9);
  assert.equal(computeFitZoom({ availableWidth: 1600, outputWidth: 1155 }), 1);
});

test('computeStageAvailableWidth ignores transient scrollbar width during mobile fit', () => {
  const { computeStageAvailableWidth } = require('../app.js');
  assert.equal(computeStageAvailableWidth({ rectWidth: 353, paddingLeft: 8, paddingRight: 8 }), 337);
});

test('selectPreRenderZoom measures mobile auto-fit from an unzoomed grid', () => {
  const { selectPreRenderZoom } = require('../app.js');
  assert.equal(selectPreRenderZoom({ autoFit: true, isMobile: true, requestedZoom: 0.29 }), 1);
  assert.equal(selectPreRenderZoom({ autoFit: false, isMobile: true, requestedZoom: 0.29 }), 0.29);
  assert.equal(selectPreRenderZoom({ autoFit: true, isMobile: false, requestedZoom: 1.5 }), 1.5);
});
