const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const renderer = require('../text-renderer.js');

const root = path.resolve(__dirname, '..');
const read = (name) => fs.readFileSync(path.join(root, name), 'utf8');

test('visible renderer does not create image elements or per-cell backgrounds', () => {
  const js = read('text-renderer.js');
  assert.doesNotMatch(js, /createElement\(['"]img['"]\)/);
  assert.doesNotMatch(js, /\.glyph-cell[^\n]*background/i);
  assert.match(js, /textContent\s*=/);
});

test('groupCellsIntoRows preserves exact grid order', () => {
  const cells = [
    { x: 1, y: 1, glyph: '4' },
    { x: 0, y: 0, glyph: '1' },
    { x: 1, y: 0, glyph: '2' },
    { x: 0, y: 1, glyph: '3' },
  ];
  const rows = renderer.groupCellsIntoRows(cells, 2);
  assert.deepEqual(rows.map((row) => row.map((c) => c.glyph)), [['1', '2'], ['3', '4']]);
});

test('renderer source uses spans and foreground color', () => {
  const js = read('text-renderer.js');
  assert.match(js, /createElement\(['"]span['"]\)/);
  assert.match(js, /style\.color\s*=/);
  assert.match(js, /glyph-row/);
  assert.match(js, /glyph-cell/);
});

test('visual lab exposes required controls and keeps source outside digit output', () => {
  const html = read('index.html');
  assert.match(html, /id="digit-output"/);
  assert.match(html, /id="source-file"/);
  assert.match(html, /assets\/benchmark-day\.png/);
  assert.match(html, /id="columns"[^>]*value="240"/);
  for (const id of ['density','shape','edge','continuity','saturation','contrast','gamma','min-brightness','zoom','reset','status-font','status-aspect','status-rows']) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(html, /id="source-debug-panel"[^>]*hidden/);
  const outputMatch = html.match(/<div id="digit-output"[^>]*>([\s\S]*?)<\/div>/);
  assert.ok(outputMatch);
  assert.doesNotMatch(outputMatch[1], /<img\b/i);
});

test('glyph cells never receive CSS backgrounds', () => {
  const css = read('styles.css');
  const block = css.match(/\.glyph-cell\s*\{([\s\S]*?)\}/);
  assert.ok(block);
  assert.doesNotMatch(block[1], /background/i);
});

test('stage scroll contains zoomed glyph surface instead of stretching the page', () => {
  const css = read('styles.css');
  const block = css.match(/\.stage-scroll\s*\{([\s\S]*?)\}/);
  assert.ok(block);
  assert.match(block[1], /max-height\s*:/);
  assert.doesNotMatch(block[1], /min-height\s*:\s*72vh/);
});

test('mobile lab keeps the image first and allows a fit-width zoom', () => {
  const css = read('styles.css');
  const html = read('index.html');
  assert.doesNotMatch(css, /order\s*:\s*-1/);
  assert.match(html, /id="zoom"[^>]*min="20"/);
});
