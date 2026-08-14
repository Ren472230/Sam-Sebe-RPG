# Visual v4 HTML Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone browser prototype of the village screen using real ASCII/textmode HTML with switchable day/night presentation and a visual-novel dialogue layer.

**Architecture:** The prototype lives in `prototype/visual-v4/` and uses only static HTML, CSS, and plain JavaScript. Scene geometry is a shared semantic ASCII model rendered into browser text spans; day/night changes are applied through `data-theme` and CSS custom properties so geometry stays identical while palette and lighting tokens change.

**Tech Stack:** HTML5, CSS custom properties, vanilla JavaScript, Node.js built-in `node:test` for zero-dependency checks.

## Global Constraints

- No generated raster image is used as the scene.
- No WebGL, `textmode.js`, `rot.js`, framework, bundler, or external runtime dependency.
- The prototype must run by opening `prototype/visual-v4/index.html` directly.
- The same ASCII scene geometry is used for day and night.
- Day is brighter and more colorful; night is darker and more atmospheric without crushing landmark readability.
- The world remains visually dominant over UI.
- Controls must be real buttons with keyboard focus states.
- Respect `prefers-reduced-motion`.

---

### Task 1: Lock the static screen contract

**Files:**
- Create: `prototype/visual-v4/tests/visual-v4.test.cjs`
- Create: `prototype/visual-v4/index.html`

**Interfaces:**
- Consumes: approved Visual v4 design specification.
- Produces: stable DOM IDs/classes used by styling and JavaScript: `#game`, `#scene`, `#theme-toggle`, `#theme-label`, `.choice`, `.memory-line`.

- [ ] **Step 1: Write the failing static contract test**

```js
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
  assert.equal((html.match(/class="choice/g) || []).length, 3);
  assert.match(html, /Память мира: вчера ты кормил ворона у колодца/);
  assert.match(html, /Мира/);
});
```

- [ ] **Step 2: Run test and confirm RED**

Run: `node --test prototype/visual-v4/tests/visual-v4.test.cjs`
Expected: FAIL because `index.html` does not exist.

- [ ] **Step 3: Implement minimal semantic HTML**

Create a 16:9-oriented game shell with the top context strip, dominant `#scene`, visual-novel dialogue block, three real `<button class="choice">` controls, day/night `<button id="theme-toggle">`, and the memory line. Reference local `styles.css` and `app.js` only.

- [ ] **Step 4: Run test and confirm GREEN**

Run: `node --test prototype/visual-v4/tests/visual-v4.test.cjs`
Expected: PASS for the static screen contract.

- [ ] **Step 5: Commit**

```bash
git add prototype/visual-v4/index.html prototype/visual-v4/tests/visual-v4.test.cjs
git commit -m "feat: scaffold Visual v4 game screen"
```

### Task 2: Build the shared ASCII scene and day/night behavior

**Files:**
- Modify: `prototype/visual-v4/tests/visual-v4.test.cjs`
- Create: `prototype/visual-v4/app.js`

**Interfaces:**
- Produces: `getThemeContext(theme)`, `nextTheme(theme)`, `buildSceneHtml()`, `applyTheme(root, label, theme)`, `selectChoice(buttons, selectedButton)`.
- `SCENE_LINES` is one shared semantic scene definition for both themes.

- [ ] **Step 1: Add failing behavior tests**

```js
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
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `node --test prototype/visual-v4/tests/visual-v4.test.cjs`
Expected: FAIL because `app.js` and exported behavior do not exist.

- [ ] **Step 3: Implement minimal JavaScript behavior**

Define one semantic ASCII scene array. `buildSceneHtml()` converts rows/segments into escaped text spans carrying classes such as `sky`, `leaf`, `wood`, `stone`, `road`, `shadow`, `moonlit`, `warm-light`, `hot-light`, and `focal`. Add browser initialization that renders the scene, toggles `data-theme` between `day` and `night`, updates top-bar copy, and selects one dialogue choice at a time. Export pure helpers through `module.exports` when running under Node.

- [ ] **Step 4: Run tests and confirm GREEN**

Run: `node --test prototype/visual-v4/tests/visual-v4.test.cjs`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add prototype/visual-v4/app.js prototype/visual-v4/tests/visual-v4.test.cjs
git commit -m "feat: add shared ASCII scene and theme behavior"
```

### Task 3: Finish the visual system and responsive readability

**Files:**
- Modify: `prototype/visual-v4/tests/visual-v4.test.cjs`
- Create: `prototype/visual-v4/styles.css`
- Modify: `prototype/visual-v4/index.html`

**Interfaces:**
- CSS consumes semantic scene classes and `[data-theme="day|night"]` state.
- Produces no runtime dependency; all presentation is native CSS.

- [ ] **Step 1: Add failing visual-contract tests**

```js
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
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `node --test prototype/visual-v4/tests/visual-v4.test.cjs`
Expected: FAIL because `styles.css` does not exist.

- [ ] **Step 3: Implement the final presentation**

Create a restrained textmode visual system: daytime with readable blue sky, green vegetation, warm wood and earth; nighttime with visible blue-gray midtones plus local amber forge/window accents. Keep borders subtle, scene dominant, dialogue panel high-contrast, selected choice marked by both arrow/shape and color, and support narrow widths without converting the screen into a dashboard.

- [ ] **Step 4: Run full automated verification**

Run: `node --test prototype/visual-v4/tests/visual-v4.test.cjs`
Expected: all tests PASS with zero warnings/errors.

- [ ] **Step 5: Browser smoke verification**

Open `prototype/visual-v4/index.html` directly. Verify repeated day/night toggling, all three choices, readable landmarks in both themes, no external network requests, and no destructive overflow at a narrow viewport.

- [ ] **Step 6: Commit**

```bash
git add prototype/visual-v4
git commit -m "feat: finish Visual v4 day night ASCII prototype"
```

## Final verification

Run:

```bash
node --test prototype/visual-v4/tests/visual-v4.test.cjs
git status --short
```

Expected: tests pass and only intentional implementation files are present. Then compare the feature branch against `main` and review the complete diff before delivery.
