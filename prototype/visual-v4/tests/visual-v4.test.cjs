const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = (name) => fs.readFileSync(path.join(root, name), 'utf8');

test('screen exposes the ASCII scene, theme control, dialogue choices and world memory', () => {
  const html = read('index.html');
  assert.match(html, /id="game"[^>]*data-theme="day"/);
  assert.match(html, /id="scene"/);
  assert.match(html, /id="theme-toggle"/);
  assert.match(html, /id="theme-label"/);
  assert.equal((html.match(/<button class="choice(?: is-selected)?"/g) || []).length, 3);
  assert.match(html, /Память мира: вчера ты кормил ворона у колодца/);
  assert.match(html, /Мира/);
});

test('theme copy differentiates day and night', () => {
  const app = require('../app.js');
  assert.equal(app.getThemeContext('day').label, 'День');
  assert.equal(app.getThemeContext('night').label, 'Ночь');
  assert.equal(app.nextTheme('day'), 'night');
  assert.equal(app.nextTheme('night'), 'day');
});

test('shared scene contains the required landmarks as real glyph text', () => {
  const app = require('../app.js');
  const scene = app.buildSceneHtml();
  assert.match(scene, /@/);
  assert.match(scene, /ВОРОН/);
  assert.match(scene, /КОЛОДЕЦ/);
  assert.match(scene, /КУЗНИЦА/);
  assert.match(scene, /ТАВЕРНА/);
  assert.match(scene, /МИРА/);
  assert.doesNotMatch(scene, /<img/i);
});

test('styles define separate day/night palettes and semantic light tokens', () => {
  const css = read('styles.css');
  assert.match(css, /\[data-theme="day"\]/);
  assert.match(css, /\[data-theme="night"\]/);
  for (const token of ['warm-light', 'hot-light', 'moonlit', 'shadow', 'focal']) {
    assert.match(css, new RegExp('\\.' + token));
  }
  assert.match(css, /prefers-reduced-motion/);
  assert.match(css, /@media \(max-width:/);
});
