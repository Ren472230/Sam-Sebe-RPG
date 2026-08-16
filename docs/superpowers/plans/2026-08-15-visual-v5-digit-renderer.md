# Visual v5 Digit Renderer v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone browser-based converter that turns one attractive daytime village illustration into a deterministic 240-column image made exclusively from real colored `0–9 . : -` glyphs on a dark background.

**Architecture:** Keep the conversion pipeline independent from game state: glyph profiling -> source sampling -> glyph scoring/color correction -> render model -> DOM text renderer. Browser Canvas 2D is used only for offscreen analysis; the visible output is real text glyphs. The first milestone is a visual lab with a bundled benchmark image and upload support, not the final game screen.

**Tech Stack:** Plain HTML/CSS/JavaScript, Canvas 2D, DOM, Node.js built-in `node:test` for deterministic pure-function tests, no bundler, no runtime dependency.

## Global Constraints

- Output glyph set is exactly `0 1 2 3 4 5 6 7 8 9 . : -`, plus one optional explicit `@` player marker.
- Default output width is exactly 240 columns.
- Output row count is derived from source aspect ratio and measured glyph-cell aspect ratio.
- Each visible cell has only a foreground glyph and foreground RGB color.
- All cells share one global near-black background; no sampled per-cell background colors.
- The source raster must not be visible beneath or above the rendered glyph surface.
- No `░▒▓`, box-drawing characters, CRT scanlines, terminal glow, or hacker aesthetic.
- v1 uses native browser APIs only; do not add `textmode.js` or `rot.js` unless a measured blocker is demonstrated.
- The main quality gate is visual: tests prove determinism/contracts, but browser screenshots and direct inspection decide whether the renderer is good enough.
- Keep this prototype separate from `src/samseberpg/` and from the old Visual v4 implementation.

---

## Planned file map

- `prototype/visual-v5-digit-renderer/index.html` — visual lab shell and controls.
- `prototype/visual-v5-digit-renderer/styles.css` — page layout, glyph surface, dark background, responsive behavior.
- `prototype/visual-v5-digit-renderer/app.js` — bootstrap, source loading, control binding, conversion orchestration.
- `prototype/visual-v5-digit-renderer/glyph-profiler.js` — font-cell measurement, glyph rasterization, mask feature extraction.
- `prototype/visual-v5-digit-renderer/image-sampler.js` — grid geometry, source-region sampling, luminance/color/gradient features.
- `prototype/visual-v5-digit-renderer/glyph-mapper.js` — deterministic scoring, color correction, marker override.
- `prototype/visual-v5-digit-renderer/text-renderer.js` — DOM render model and visible real-glyph output.
- `prototype/visual-v5-digit-renderer/assets/benchmark-day.png` — fixed daytime village benchmark image.
- `prototype/visual-v5-digit-renderer/tests/glyph-profiler.test.cjs` — mask feature tests.
- `prototype/visual-v5-digit-renderer/tests/image-sampler.test.cjs` — geometry and sampling tests.
- `prototype/visual-v5-digit-renderer/tests/glyph-mapper.test.cjs` — scoring, determinism, color correction and marker tests.
- `prototype/visual-v5-digit-renderer/tests/contracts.test.cjs` — static contract checks for HTML/CSS/allowed glyphs/no raster overlay.

---

### Task 1: Grid geometry and source sampling core

**Files:**
- Create: `prototype/visual-v5-digit-renderer/image-sampler.js`
- Create: `prototype/visual-v5-digit-renderer/tests/image-sampler.test.cjs`

**Interfaces:**
- Produces `computeGridGeometry({ sourceWidth, sourceHeight, columns, cellAspect }) -> { columns, rows, sourceAspect, cellAspect }`.
- Produces `sampleImageGrid({ data, width, height }, geometry, { patchWidth = 4, patchHeight = 6 }) -> SampleCell[]`.
- `SampleCell` shape: `{ x, y, rgb: [r,g,b], luminance, variance, gradientX, gradientY, patch }`.
- `patch` is a normalized `patchWidth * patchHeight` luminance array in row-major order.

- [ ] **Step 1: Write failing geometry and sampler tests.**

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const sampler = require('../image-sampler.js');

test('computeGridGeometry preserves source aspect using measured cell aspect', () => {
  const g = sampler.computeGridGeometry({
    sourceWidth: 1600,
    sourceHeight: 900,
    columns: 240,
    cellAspect: 1,
  });
  assert.equal(g.columns, 240);
  assert.equal(g.rows, 135);
});

test('sampleImageGrid averages more than one source pixel per cell in linear light', () => {
  const rgba = new Uint8ClampedArray([
    255,0,0,255, 0,255,0,255,
    0,0,255,255, 255,255,255,255,
  ]);
  const cells = sampler.sampleImageGrid(
    { data: rgba, width: 2, height: 2 },
    { columns: 1, rows: 1 },
    { patchWidth: 2, patchHeight: 2 }
  );
  assert.equal(cells.length, 1);
  assert.ok(cells[0].rgb[0] > 180 && cells[0].rgb[0] < 195);
  assert.ok(cells[0].variance > 0);
  assert.equal(cells[0].patch.length, 4);
});
```

- [ ] **Step 2: Run tests and verify failure.**

```bash
node --test prototype/visual-v5-digit-renderer/tests/image-sampler.test.cjs
```
Expected: FAIL because `image-sampler.js` does not exist.

- [ ] **Step 3: Implement the pure sampling API.** Use sRGB -> linear conversion before averaging, convert the averaged channels back to sRGB for `rgb`, use Rec.709 luminance weights in linear light, finite-difference gradients from the normalized patch, and the exact row formula below.

```js
function computeGridGeometry({ sourceWidth, sourceHeight, columns = 240, cellAspect }) {
  const sourceAspect = sourceWidth / sourceHeight;
  const rows = Math.max(1, Math.round((columns * cellAspect) / sourceAspect));
  return { columns, rows, sourceAspect, cellAspect };
}
```

- [ ] **Step 4: Run focused tests and confirm PASS.**

```bash
node --test prototype/visual-v5-digit-renderer/tests/image-sampler.test.cjs
```

- [ ] **Step 5: Commit.**

```bash
git add prototype/visual-v5-digit-renderer/image-sampler.js prototype/visual-v5-digit-renderer/tests/image-sampler.test.cjs
git commit -m "feat: add digit renderer image sampler"
```

---

### Task 2: Real-font glyph profiling

**Files:**
- Create: `prototype/visual-v5-digit-renderer/glyph-profiler.js`
- Create: `prototype/visual-v5-digit-renderer/tests/glyph-profiler.test.cjs`

**Interfaces:**
- Allowed glyph constant: `ALLOWED_GLYPHS = ['0','1','2','3','4','5','6','7','8','9','.',':','-']`.
- Produces pure `analyzeMask(mask, width, height) -> GlyphFeatures`.
- `GlyphFeatures`: `{ density, centerX, centerY, horizontal, vertical, edgeX, edgeY, patch }`.
- Browser-only `profileFont({ fontFamily, fontSize, lineHeight, glyphs = ALLOWED_GLYPHS, patchWidth = 4, patchHeight = 6 }) -> { fontFamily, fontSize, lineHeight, cellWidth, cellHeight, cellAspect, profiles }`.
- `cellAspect = cellWidth / cellHeight`.
- `profiles` maps each glyph to `GlyphFeatures` plus its original mask.

- [ ] **Step 1: Write failing pure mask tests.**

```js
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
```

- [ ] **Step 2: Run and verify failure.**

```bash
node --test prototype/visual-v5-digit-renderer/tests/glyph-profiler.test.cjs
```

- [ ] **Step 3: Implement `analyzeMask` and browser-only `profileFont`.** Rasterize each glyph as white ink on transparent black in an offscreen Canvas 2D context, read alpha as the mask, measure cell width with `ctx.measureText('0').width`, use the supplied `lineHeight` as `cellHeight`, and profile the same font metrics that the visible DOM renderer will use.

- [ ] **Step 4: Ensure module works in browser and Node.** Use an IIFE exposing `window.DigitGlyphProfiler` in browser and `module.exports` in Node.

- [ ] **Step 5: Run focused tests and commit.**

```bash
node --test prototype/visual-v5-digit-renderer/tests/glyph-profiler.test.cjs
git add prototype/visual-v5-digit-renderer/glyph-profiler.js prototype/visual-v5-digit-renderer/tests/glyph-profiler.test.cjs
git commit -m "feat: profile real digit glyph shapes"
```

---

### Task 3: Deterministic glyph mapper and foreground color correction

**Files:**
- Create: `prototype/visual-v5-digit-renderer/glyph-mapper.js`
- Create: `prototype/visual-v5-digit-renderer/tests/glyph-mapper.test.cjs`

**Interfaces:**
- Default weights: `{ density: 0.40, shape: 0.35, edge: 0.20, continuity: 0.05 }`.
- Default color tuning: `{ saturation: 1.20, contrast: 1.08, gamma: 1.00, minBrightness: 0.16 }`.
- Produces `scoreGlyph(sample, profile, previousGlyph, weights) -> number` where lower is better.
- Produces `chooseGlyph(sample, profiles, previousGlyph, weights) -> glyph`.
- Produces `correctForegroundColor([r,g,b], tuning) -> [r,g,b]`.
- Produces `mapSamples(samples, profiles, options) -> RenderCell[]`.
- `RenderCell`: `{ x, y, glyph, color: [r,g,b] }`.
- `options` shape: `{ weights, color, columns, rows, marker }`.
- `options.marker` may be `{ normalizedX, normalizedY, glyph: '@', color: [255,240,170] }`.

- [ ] **Step 1: Write failing scoring/determinism/color tests.**

```js
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
```

- [ ] **Step 2: Run and verify failure.**

```bash
node --test prototype/visual-v5-digit-renderer/tests/glyph-mapper.test.cjs
```

- [ ] **Step 3: Implement mapper.** Compute mean absolute patch error, density error, gradient-direction error and continuity penalty. Iterate glyphs in the canonical allowed-glyph order so ties are deterministic.

- [ ] **Step 4: Implement color correction in normalized RGB.** Saturation operates around luminance, contrast around 0.5, gamma on each channel, then scale upward only when maximum channel is below `minBrightness`.

- [ ] **Step 5: Implement marker override.** Convert normalized marker coordinates to one exact grid cell using `columns` and `rows` after the normal map pass. Do not use image recognition for the player.

- [ ] **Step 6: Run tests and commit.**

```bash
node --test prototype/visual-v5-digit-renderer/tests/glyph-mapper.test.cjs
git add prototype/visual-v5-digit-renderer/glyph-mapper.js prototype/visual-v5-digit-renderer/tests/glyph-mapper.test.cjs
git commit -m "feat: map image samples to real colored digits"
```

---

### Task 4: Real DOM glyph renderer with no raster overlay

**Files:**
- Create: `prototype/visual-v5-digit-renderer/text-renderer.js`
- Create: `prototype/visual-v5-digit-renderer/tests/contracts.test.cjs`

**Interfaces:**
- Produces `groupCellsIntoRows(cells, columns) -> RenderCell[][]`.
- Browser-only `renderTextGrid(root, cells, { columns, rows, cellWidth, cellHeight, fontFamily, fontSize, lineHeight, background })`.
- Visible output uses `.glyph-row` elements containing `.glyph-cell` spans whose `textContent` is one actual glyph.
- `.glyph-cell` receives foreground `style.color` only; no per-cell background property.

- [ ] **Step 1: Write failing contract tests.**

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = (name) => fs.readFileSync(path.join(root, name), 'utf8');

test('visible renderer does not create image elements or per-cell backgrounds', () => {
  const js = read('text-renderer.js');
  assert.doesNotMatch(js, /createElement\(['"]img['"]\)/);
  assert.doesNotMatch(js, /style\.background(Color)?\s*=/);
  assert.match(js, /textContent\s*=/);
});
```

- [ ] **Step 2: Run and verify failure.**

```bash
node --test prototype/visual-v5-digit-renderer/tests/contracts.test.cjs
```

- [ ] **Step 3: Implement render model grouping and DOM rendering.** Use `DocumentFragment` per row, set fixed `width`/`height` from measured cell metrics, set `font-family`, `font-size`, `line-height`, `white-space: pre`, and only set `span.style.color` per cell.

- [ ] **Step 4: Add an optional `data-glyph` attribute only for debugging; do not add hidden raster nodes.**

- [ ] **Step 5: Run tests and commit.**

```bash
node --test prototype/visual-v5-digit-renderer/tests/contracts.test.cjs
git add prototype/visual-v5-digit-renderer/text-renderer.js prototype/visual-v5-digit-renderer/tests/contracts.test.cjs
git commit -m "feat: render digit grid as real DOM glyphs"
```

---

### Task 5: Standalone visual lab and benchmark source

**Files:**
- Create: `prototype/visual-v5-digit-renderer/index.html`
- Create: `prototype/visual-v5-digit-renderer/styles.css`
- Create: `prototype/visual-v5-digit-renderer/app.js`
- Create: `prototype/visual-v5-digit-renderer/assets/benchmark-day.png`
- Modify: `prototype/visual-v5-digit-renderer/tests/contracts.test.cjs`

**Interfaces:**
- `app.js` exports pure `buildSettings(formValues)` and browser `initDigitLab(document)`.
- Default settings: `columns=240`, mapper weights and color tuning from Task 3.
- Default marker normalized position for benchmark: `{ normalizedX: 0.68, normalizedY: 0.76 }`; UI can toggle marker off.
- Source image is hidden by default and appears only when debug checkbox `#show-source` is enabled.
- Status UI shows measured `rows`, `cellAspect`, active font, and conversion duration.

- [ ] **Step 1: Extend static tests for the visual-lab contract.** Assert the page contains `#digit-output`, file input, bundled benchmark source, 240-column control, tuning controls, zoom, reset, font/aspect/row status fields, and hidden-by-default source debug panel. Assert no `<img>` exists inside `#digit-output`.

- [ ] **Step 2: Run contract tests and verify failure.**

```bash
node --test prototype/visual-v5-digit-renderer/tests/contracts.test.cjs
```

- [ ] **Step 3: Add the approved daytime village benchmark image as `assets/benchmark-day.png`.** This asset is input material only and must never be placed inside the digit output container.

- [ ] **Step 4: Build the page shell.** The digit image must occupy the main central area. Put compact tuning controls in a narrow side panel. Keep UI neutral and subordinate; no terminal chrome, scanlines or decorative ASCII.

- [ ] **Step 5: Wire the conversion pipeline in `app.js`.** Exact orchestration:

```js
const font = await DigitGlyphProfiler.profileFont(settings.font);
const geometry = DigitImageSampler.computeGridGeometry({
  sourceWidth: image.naturalWidth,
  sourceHeight: image.naturalHeight,
  columns: settings.columns,
  cellAspect: font.cellAspect,
});
const imageData = sourceContext.getImageData(0, 0, sourceCanvas.width, sourceCanvas.height);
const samples = DigitImageSampler.sampleImageGrid(
  { data: imageData.data, width: imageData.width, height: imageData.height },
  geometry,
  settings.patch
);
const cells = DigitGlyphMapper.mapSamples(samples, font.profiles, {
  weights: settings.weights,
  color: settings.color,
  columns: geometry.columns,
  rows: geometry.rows,
  marker: settings.marker,
});
DigitTextRenderer.renderTextGrid(output, cells, {
  ...geometry,
  ...font,
  background: settings.background,
});
```

- [ ] **Step 6: Debounce tuning changes by 120 ms and reuse cached source sampling when only mapper/color weights change.** Reprofile/resample only when font, line-height, columns or source changes.

- [ ] **Step 7: Run all Node tests.**

```bash
node --test prototype/visual-v5-digit-renderer/tests/*.test.cjs
```
Expected: all PASS.

- [ ] **Step 8: Commit.**

```bash
git add prototype/visual-v5-digit-renderer
git commit -m "feat: add Visual v5 digit renderer lab"
```

---

### Task 6: Browser proof that the result is truly text, then visual tuning

**Files:**
- Modify only as evidence requires: `prototype/visual-v5-digit-renderer/styles.css`, `glyph-profiler.js`, `glyph-mapper.js`, `app.js`.
- No game UI files.

**Interfaces:**
- Final benchmark remains the bundled daytime source at 240 columns.
- Visual QA must inspect both normal view and 300% zoom.

- [ ] **Step 1: Start a local static server.**

```bash
python3 -m http.server 4173 --directory prototype/visual-v5-digit-renderer
```

- [ ] **Step 2: Open `http://127.0.0.1:4173/` in a real browser and verify page identity, no blank screen, no runtime errors, and that the benchmark renders automatically.**

- [ ] **Step 3: Inspect the DOM.** Confirm `#digit-output` contains thousands of `.glyph-cell` spans, each has one actual character, and contains no `<img>`, `<canvas>` or colored background tiles as visible scene layers.

- [ ] **Step 4: Capture a normal-view screenshot and a 300% zoom screenshot.** At normal view judge scene readability; at 300% verify the digits are unmistakably actual text.

- [ ] **Step 5: Compare against the quality gates in the spec.** Inspect sky, red forge roof, blue tavern roof, road, well, vegetation, Mira/player silhouette, and dark structural details. Record failures as mapper/color/font issues rather than changing the game composition.

- [ ] **Step 6: Tune one variable at a time only when screenshot evidence requires it:** mapper weights (`density`, `shape`, `edge`, `continuity`), color tuning (`saturation`, `contrast`, `gamma`, `minBrightness`), or font size/line-height while preserving measured geometry. After each change, rerun the same screenshot pair and keep the change only if scene readability improves without creating colored rectangle-like cells.

- [ ] **Step 7: Re-run all tests after visual tuning.**

```bash
node --test prototype/visual-v5-digit-renderer/tests/*.test.cjs
pytest -q
```
Expected: JavaScript prototype tests PASS and existing Python shared-world suite remains green.

- [ ] **Step 8: Commit the verified tuning.**

```bash
git add prototype/visual-v5-digit-renderer
git commit -m "refine: tune Visual v5 digit renderer output"
```

---

### Task 7: Final visual handoff, no premature game integration

**Files:**
- Modify: `README.md` only if a short prototype run command is useful.
- Do not merge into the final game screen yet.

**Interfaces:**
- Deliverable URL: local `prototype/visual-v5-digit-renderer/index.html` via static server.
- Deliverable evidence: normal-view screenshot + zoomed screenshot proving real digits.

- [ ] **Step 1: Run the complete verification set from a clean checkout/branch state.**

```bash
node --test prototype/visual-v5-digit-renderer/tests/*.test.cjs
pytest -q
```

- [ ] **Step 2: Verify deterministic re-render.** Reload the page twice with identical settings and confirm the glyph grid and colors are unchanged.

- [ ] **Step 3: Present the actual rendered HTML result to the user before implementing night mode, dialogue UI, Discord embedding or animation.** The question at this gate is only: “Is this digit image visually good enough to keep?”

- [ ] **Step 4: If the user rejects the image, keep work inside this renderer branch and iterate only on source suitability, profiler, sampler, mapper, font, or color transform. Do not proceed to game integration.**

- [ ] **Step 5: If the user accepts the image, document the accepted tuning preset and only then open a separate design cycle for night rendering and integration into the game screen.**

## Completion gate

Digit Renderer v1 is complete only when the standalone HTML page automatically renders the benchmark village at 240 columns as thousands of actual selectable/inspectable `0–9 . : -` DOM glyphs on one near-black background, no raster scene is visible in the output, the result is deterministic, all JavaScript and existing Python tests pass, normal-view and 300% screenshots verify the text nature of the render, and the user has seen the actual rendered image before any further Visual v5 integration begins.
