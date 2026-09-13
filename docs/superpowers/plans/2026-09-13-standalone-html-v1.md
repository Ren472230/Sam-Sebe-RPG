# Standalone HTML v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build a dark-theme, fully offline, one-file playable Sam-Sebe-RPG vertical slice with embedded visuals, deterministic world progression, causal NPC knowledge and portable save slots.

**Architecture:** Source stays split into small plain-JavaScript modules so Node can test them and the build step can assemble one browser file. The shipped HTML contains inline CSS, inline SVG gameplay scenes and embedded generated concept art, with no network runtime dependency.

**Tech Stack:** Plain JavaScript, Node.js built-in test runner, DOM/SVG, CSS, localStorage, deterministic build script, Chromium browser acceptance.

**Spec:** `docs/superpowers/specs/2026-09-13-standalone-html-v1-design.md`

## Global constraints

- Final artifact: `standalone/dist/sam-sebe-rpg.html`.
- Opens as one file and has no remote scripts, fonts, images, API calls or CDN dependencies.
- Dark graphite theme is the only v1 theme.
- Existing server-backed game remains isolated and unchanged.
- Standalone saves use `gameId = sam-sebe-rpg-standalone` and schema version 1.
- Generated concept art and SVG gameplay visuals are embedded in the final file.
- World simulation is deterministic and renderer timing cannot change outcomes.

## Task 1 – Deterministic portable game domain

Create `standalone/src/domain/state.js`, `world.js`, `dialogue.js`, `reducer.js` and `standalone/tests/domain.test.js`.

RED → GREEN requirements:
- fresh state;
- Oren firewood quest start/completion;
- three distinct wood piles;
- reward exactly once;
- WAIT progression;
- Talen arrival exactly once at tick 10;
- eastern-road knowledge starts with Talen;
- grounded transfer to Oren after contact beat;
- Mira/Kaspar remain unaware;
- same serialized state + same action produces same state.

## Task 2 – Three-slot resilient saves

Create `standalone/src/save/save-store.js` and `standalone/tests/save.test.js`.

Requirements:
- 3 isolated slots;
- autosave envelope;
- latest-known-good backup;
- corrupt-primary recovery;
- export/import JSON;
- wrong game id rejection;
- future schema rejection;
- browser-storage fallback for environments that block persistent storage.

## Task 3 – Dark playable UI and SVG world

Create `standalone/src/view/world-view.js`, `standalone/src/input/input-map.js`, `standalone/src/ui/app.js`, `standalone/src/debug/dev-tools.js`, `standalone/styles.css`, `standalone/template.html`.

Requirements:
- dark graphite/milk/scarlet/turquoise/amber palette;
- playable village and tavern SVG scenes;
- WASD/arrows + E;
- screen D-pad for touch fallback;
- modal input blocking;
- journal, dialogue, quest and world-event surfaces;
- save/import/export UI;
- playfield remains primary.

## Task 4 – Embedded generated art and one-file build

Create `standalone/scripts/build.mjs`, generated concept-art asset, and `standalone/tests/build.test.js`.

Requirements:
- exactly one distributable HTML;
- embedded generated concept art;
- inline CSS/JS/SVG;
- no unresolved build markers;
- no runtime `http://` or `https://` dependency;
- no external script or stylesheet tags.

## Task 5 – Browser acceptance

Create a browser smoke route that performs the real route with keyboard and UI actions:

1. start slot;
2. walk to tavern;
3. talk to Oren;
4. accept quest;
5. leave tavern;
6. collect all three wood piles;
7. return and deliver;
8. verify 10-coin reward;
9. advance world;
10. verify Talen appears and eastern-road event reaches Oren;
11. capture title and gameplay screenshots;
12. rerun domain/save/UI/build suites on the final artifact.

The managed execution environment may block direct `file://` navigation by browser policy; when that happens, browser runtime is exercised by loading the exact final HTML document directly into Chromium, while offline/file portability is verified structurally by the absence of external runtime dependencies.
