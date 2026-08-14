# Visual v4 HTML — Design Specification

## Goal

Create a browser-based visual prototype of the game's core presentation for first playtesters. The prototype must use real HTML/CSS/JavaScript and real ASCII/textmode scene construction rather than generated raster imagery.

The purpose is to validate whether the project's visual language is pleasant, readable, atmospheric, and distinctive enough for early testers before investing in a heavier renderer.

## Scope

Included:
- one complete game screen;
- one persistent village scene;
- real ASCII/textmode scene content rendered from text/glyph elements in the browser;
- daytime and nighttime presentation modes for the same scene;
- a manual day/night toggle for visual review;
- visual-novel style dialogue area;
- NPC speaker name and dialogue;
- three player response choices;
- small contextual state labels;
- a subtle world-memory line;
- responsive behavior for desktop and narrower browser widths;
- no build step and no external runtime dependency for the first prototype.

Excluded:
- generated image used as the scene itself;
- WebGL renderer;
- textmode.js integration;
- rot.js integration;
- dynamic shadows;
- real simulation state;
- Discord integration;
- inventory screens;
- combat UI;
- full map UI;
- procedural scene generation;
- animations beyond small optional UI transitions.

## Visual direction

Working style name: **Living illuminated textmode**.

The world is represented through readable glyphs and colored character groups, not raster pixel art. The scene should feel handcrafted and game-like rather than like a terminal emulator, hacker UI, generic retro website, or dense roguelike dashboard.

The world is the primary visual surface. UI is subordinate.

Avoid:
- heavy CRT scanlines;
- global glow;
- bright outlines around every object;
- excessive black crush;
- monochrome green-terminal aesthetics;
- ornate dark-fantasy decoration that reduces readability;
- permanent panels for every stat/system.

## Screen composition

Desktop target: approximately 16:9.

### Top context bar

A thin contextual strip contains:
- time of day;
- weather/ambient condition;
- village name;
- small status items: trust, coins, reputation.

It must visually recede behind the scene.

### Main world scene

The main scene occupies roughly 60–65% of the screen height and is the dominant element.

The same scene geometry is used in both day and night modes.

Required landmarks:
- village square / dirt road;
- workshop / forge;
- warm house or tavern;
- well;
- fences;
- crates / barrels / benches;
- grass and vegetation;
- raven on a post near the well;
- player represented by `@`;
- Mira visible near the workshop.

The scene is assembled from monospaced text/glyph rows and semantic spans/classes that allow different parts of the world to have different colors.

### Dialogue area

The lower portion behaves like a visual novel rather than a roguelike log.

Contains:
- speaker name: `Мира`;
- dialogue text;
- three selectable responses;
- one selected/hovered state;
- optional compact ASCII portrait or symbolic speaker block, only if it remains readable and does not consume too much space.

Initial dialogue:

> Ты снова пришёл к мастерской так поздно. В деревне говорят, что вороны что-то чувствуют перед переменами.

Choices:
1. Спросить о воронах
2. Показать найденный камень
3. Осмотреть площадь

### Footer memory line

One small low-priority line demonstrates persistent-world flavor:

`Память мира: вчера ты кормил ворона у колодца`

## Day mode

Daytime is intentionally brighter and more colorful than the previous visual experiments.

Palette priorities:
- clear desaturated-to-medium blue sky;
- readable warm wood;
- greens with multiple muted values;
- warm earth / road;
- slate / stone neutrals;
- restrained gold accents in UI.

Requirements:
- all major landmarks readable immediately;
- dark glyphs must not disappear into local backgrounds;
- vegetation can be more saturated than at night;
- buildings should have stronger material separation;
- daytime should feel welcoming and alive rather than grim.

## Night mode

Night uses the same geometry and semantic scene layers but changes palette and lighting emphasis.

Palette priorities:
- dark desaturated blue / blue-gray environment;
- cool midtones remain visible;
- warm amber/orange around forge, windows, and lanterns;
- restrained moss greens;
- slightly brighter player/NPC focal marks.

Requirements:
- night must feel darker than day without becoming unreadable;
- important objects remain identifiable outside local light sources;
- shadows are represented mainly through lower glyph brightness and color changes, not black rectangles or strong edge outlines;
- local warm areas should create depth without turning into large glow blobs;
- no object-wide outline lighting.

## Lighting model for this prototype

The first HTML version does not implement real physical lighting.

Instead, semantic scene regions receive classes such as:
- `ambient`;
- `shadow`;
- `moonlit`;
- `warm-light`;
- `hot-light`;
- `focal`.

Day and night themes remap those tokens through CSS custom properties.

This allows rapid visual balancing now and preserves a clean migration path to textmode.js or a real light/FOV system later if tests justify it.

## Architecture

Use three files:
- `prototype/visual-v4/index.html` — semantic screen structure;
- `prototype/visual-v4/styles.css` — layout, theme variables, ASCII scene styling, responsive rules;
- `prototype/visual-v4/app.js` — day/night state, toggle behavior, choice selection.

No bundler, framework, or package dependency.

### Scene representation

Use a fixed monospaced ASCII canvas constructed as multiple lines. Individual scene features may be split into spans or line fragments with semantic classes where color control is required.

Do not draw the scene onto `<canvas>` in this version. The visual test specifically needs genuine browser text/glyph rendering.

### Theme state

Root container receives either:
- `data-theme="day"`;
- `data-theme="night"`.

All environmental color changes must flow from CSS variables rather than duplicated markup.

### Interaction

Day/night toggle:
- available at all times;
- updates theme immediately;
- also updates contextual top-bar copy.

Choices:
- hover/focus state;
- click changes the selected response visually;
- no narrative branching required in Visual v4.

## Responsive behavior

Primary evaluation is desktop.

At narrower widths:
- preserve monospaced scene proportions as far as practical;
- reduce font size and spacing before introducing horizontal scrolling;
- dialogue choices stack vertically;
- top status labels may wrap or reduce detail;
- scene must not collapse into a dashboard layout.

Mobile perfection is not required for Visual v4.

## Accessibility and readability

- sufficient text contrast in both themes;
- visible keyboard focus states;
- day/night control is a real button;
- response options are real buttons;
- respect `prefers-reduced-motion`;
- avoid using color as the only indication of selected choice.

## Visual success criteria

Visual v4 passes when:
1. a tester can immediately identify the village, road, workshop, well, raven, Mira, and player;
2. day mode feels colorful and inviting rather than dark-fantasy-heavy;
3. night mode is clearly darker and more atmospheric while all major structures remain readable;
4. the screen reads as a game, not a terminal emulator or web dashboard;
5. the ASCII/textmode construction remains obvious at normal viewing distance;
6. dialogue and choices can be read without effort;
7. switching day/night demonstrates a convincing shared-world time-of-day change using the same scene geometry;
8. the prototype runs by opening `index.html` directly with no build step.

## Verification

Before considering Visual v4 complete:
- open the HTML directly in a browser;
- verify day/night switch works repeatedly;
- verify all three choices can receive focus and selection;
- inspect both themes at desktop width;
- inspect at a narrow width for destructive overflow;
- confirm there are no generated scene images or external renderer dependencies;
- confirm major landmarks remain readable in both themes.

## Future upgrade path

Only after Visual v4 is accepted visually:
1. evaluate whether native HTML text is sufficient for the actual game;
2. if richer effects are needed, prototype `textmode.js` as the next renderer candidate;
3. evaluate `rot.js` concepts for FOV/light propagation separately;
4. keep simulation/state independent from presentation so renderer changes do not affect game rules.
