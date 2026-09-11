# Visual v5 — Digit Renderer v1 Design

## Goal

Build a deterministic image-to-textmode renderer that converts a beautiful source illustration into a real colored digit image. The final frame must be composed of actual glyphs, not an AI-generated imitation of glyphs, not pixel tiles, and not a raster image hidden behind text.

The immediate purpose is visual validation. Before integrating dialogue, game UI, Discord, or dynamic world state, we must be able to open one HTML preview and judge whether the rendered village image is genuinely attractive.

## Visual contract

The renderer must satisfy all of these constraints:

- source input is a normal raster illustration;
- output uses real glyphs from the set `0 1 2 3 4 5 6 7 8 9 . : -`;
- the player marker may use one explicit `@` glyph;
- target width is 240 columns;
- row count is derived automatically from source aspect ratio and measured glyph-cell aspect ratio;
- every output cell has a foreground glyph and foreground RGB color;
- cell background is one global dark / near-black color;
- no sampled colored rectangle is drawn behind a glyph;
- no source image is shown beneath or above the text layer;
- no `░▒▓`, box-drawing characters, CRT scanlines, terminal glow, or hacker aesthetic;
- the image must read as a coherent scene from normal viewing distance and reveal obvious real digits when zoomed in.

## Renderer strategy

### 1. Glyph profiling

The browser measures the actual selected monospaced font before conversion.

For every allowed glyph, the renderer produces a small normalized monochrome mask by rasterizing that glyph into an offscreen canvas. From the mask it records:

- ink coverage / density;
- horizontal distribution;
- vertical distribution;
- center of mass;
- coarse edge map;
- low-resolution shape signature.

This profile makes symbol selection depend on the actual font rather than on a hard-coded assumption such as `8 = dark` and `1 = light`.

The same measurement determines the real cell width-to-height ratio used when calculating the output row count.

### 2. Source sampling

The source image is scaled conceptually onto the glyph grid while preserving its aspect ratio.

Each cell samples the corresponding source region and computes:

- average linear-light RGB;
- luminance;
- luminance variance;
- local horizontal and vertical gradients;
- a low-resolution normalized luminance patch used for shape comparison.

Sampling must use more than one source pixel per cell. The source illustration is never converted by nearest-neighbour pixel lookup alone.

### 3. Glyph selection

For each source cell, all permitted glyph profiles are scored.

The initial v1 score combines:

- density error — the glyph ink density should approximate the target luminance contribution;
- shape error — the glyph mask should resemble the local luminance structure;
- edge error — glyph directional structure should reward meaningful local edges;
- continuity penalty — optional small penalty to prevent unstable visual noise when neighbouring cells are nearly identical.

The exact weights are tunable in the preview UI. The default should prioritize readable image structure over maximizing the visibility of arbitrary glyph variety.

Punctuation is allowed, but digits should dominate naturally because they provide more ink and structure. We do not force an artificial percentage of digits if the image quality becomes worse.

### 4. Glyph color

Each glyph receives a foreground RGB color derived from the source region.

The first implementation uses a perceptual correction stage rather than copying raw average RGB directly:

- optional saturation multiplier;
- optional contrast adjustment;
- optional gamma / exposure correction;
- configurable minimum foreground brightness so dark details remain visible against the dark global background.

There is no per-cell background sampling in v1.

### 5. Player marker

The normal renderer converts the whole source image. A separate optional marker layer can force one specified cell or a small anchor location to render as `@`.

This layer is deterministic and independent of image recognition. For the first visual study the position is set manually in normalized scene coordinates.

## HTML preview

The first deliverable is a standalone visual laboratory, not the final game screen.

It contains:

- image upload / bundled test-source selection;
- the digit-rendered output as the dominant surface;
- zoom control;
- 240-column default;
- measured row count display;
- font information and measured glyph aspect ratio;
- compact tuning controls for glyph size, saturation, contrast, minimum brightness, and mapper weights;
- reset button;
- optional source/reference toggle for debugging only.

The source image must be hidden by default. The user should primarily judge the real textmode output.

The output implementation may use DOM spans initially because the visual requirement explicitly benefits from proving that the result consists of real characters. If 30–50k DOM cells produce unacceptable performance, the renderer core remains independent and the display can later migrate to Canvas/WebGL text rendering without changing the conversion algorithm.

## Architecture

Keep the converter separate from game state and Visual v4.

Recommended prototype structure:

- `prototype/visual-v5-digit-renderer/index.html` — visual lab shell;
- `prototype/visual-v5-digit-renderer/styles.css` — layout and typography;
- `prototype/visual-v5-digit-renderer/app.js` — browser bootstrapping and controls;
- `prototype/visual-v5-digit-renderer/glyph-profiler.js` — font/glyph measurement;
- `prototype/visual-v5-digit-renderer/image-sampler.js` — source-region analysis;
- `prototype/visual-v5-digit-renderer/glyph-mapper.js` — scoring and glyph choice;
- `prototype/visual-v5-digit-renderer/text-renderer.js` — DOM output;
- `prototype/visual-v5-digit-renderer/tests/` — deterministic unit tests for geometry, profiling helpers, mapping, and color correction.

The conversion core should expose plain functions with no dependency on game-world code.

## Dependencies

v1 should use native browser APIs first:

- Canvas 2D for offscreen image and glyph analysis;
- DOM for visible glyph output;
- plain JavaScript, HTML, and CSS.

Do not add `textmode.js` for v1 unless browser-native rendering proves to be the quality or performance bottleneck. The important problem is the conversion algorithm, not the rendering library.

`rot.js` is out of scope; FOV and game lighting propagation are unrelated to this visual conversion milestone.

## Test source

Use the approved visual direction as a fixed first benchmark: a bright, cozy daytime fantasy village scene with a blacksmith workshop, well, road, house/tavern, vegetation, Mira, player position, and crow.

The benchmark image should have clear silhouettes and tonal separation because the renderer is being judged on its ability to preserve a strong source image, not to invent composition.

The benchmark asset is test material, not canonical game content. Replacing it later must not require renderer changes.

## Quality gates

Digit Renderer v1 is visually successful only if all of the following are true:

1. At normal viewing distance the output reads first as a village image, not random colored text.
2. At 200–400% browser zoom the cells are visibly actual `0–9 . : -` glyphs.
3. Disabling or removing the source raster does not change the visible result.
4. No per-cell colored background blocks are necessary for the scene to read.
5. Major masses survive conversion: sky, roofs, forge, road, well, vegetation, foreground character.
6. Colors remain lively enough for the requested bright daytime direction without becoming neon or oversaturated.
7. Dark structural details remain visible against the near-black background.
8. Re-rendering the same source with the same parameters is deterministic.
9. The user can change a small number of tuning parameters and see the result update without regenerating source art.

Passing unit tests or producing a technically valid grid is not sufficient. The rendered HTML must be opened and visually reviewed in a browser.

## Performance target

At 240 columns and an automatically derived row count for a 16:9 source, expect tens of thousands of glyph cells.

For v1:

- initial conversion should feel interactive on a normal desktop browser;
- parameter changes may debounce briefly;
- avoid rebuilding unrelated UI;
- if DOM rendering is the bottleneck, profile before changing architecture.

No premature WebGL optimization.

## Explicit non-goals

Digit Renderer v1 does not include:

- night rendering;
- game dialogue UI;
- inventory or HUD;
- Discord integration;
- animation;
- dynamic game lighting;
- procedural world rendering;
- AI generation of the final digit frame;
- automatic semantic recognition of NPCs or buildings;
- production asset pipeline.

These are considered only after the one-frame visual quality gate passes.

## First implementation milestone

The first milestone is deliberately narrow:

> Open one standalone HTML page containing one attractive daytime village source and see a deterministic 240-column image reconstructed exclusively from real colored glyphs on a dark background.

The milestone succeeds or fails primarily on the visible output. If the result is ugly, the next iteration changes the profiler, sampler, mapper, color transform, font, or source suitability — not the game UI.
