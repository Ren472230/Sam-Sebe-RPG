# Visual Production -> Game Integration Handoff v1

Date: 2026-08-24
Status: P0 production contract
Visual authority: MASTER STYLE REFERENCE v1 / VISUAL STYLE BIBLE v1.0

This document does **not** redefine art direction. It defines the file contract required to replace the already-validated gameplay greybox without changing game rules.

## P0 principle

Production art must drop into the existing validated route:

`village -> tavern -> Oren -> firewood quest -> completion -> reload`

The art pass must not move canonical world logic into the renderer and must not require redesigning the quest, database, dialogue contract, or interaction rules.

## Required files

Place final files under:

```text
web/public/assets/production/
  village/
    sky.webp
    far_world.webp
    mid_world.webp
    foreground.webp
  tavern/
    background.webp
    foreground.webp
  characters/
    player.webp
    oren.webp
  props/
    firewood.webp
  ui/
    dialogue_frame.webp
```

`foreground.webp` files and `ui/dialogue_frame.webp` may be omitted for the first art integration if they are not ready. All other files are P0 production inputs.

## Runtime activation gate

`web/public/assets/production/manifest.json` is the production-art switch.

- `status: "awaiting_assets"` means the validated greybox remains active and no production textures are requested.
- Commit all required P0 files first.
- Only after the required files exist at the exact manifest paths, change the manifest to `status: "ready"`.
- With `status: "ready"`, Phaser preloads the production scene layers, player, Oren and firewood under stable texture keys.
- If required scene textures fail to load, the scene falls back to the greybox rather than booting into a half-rendered state.
- Gameplay anchors, collision rectangles, quest logic and canonical state do not change when art mode changes.

Do **not** mark the manifest ready to preview a partial pack. Optional foreground/UI files may remain absent, but the required scene layers, characters and firewood must be present before activation.

## Canvas and export rules

### Village layers

Logical gameplay canvas: **960 x 540**.

All full-scene village layers must share the exact same canvas dimensions and origin so they can be stacked without manual repositioning.

- `sky.webp`: 960x540 or exact integer multiple, opaque.
- `far_world.webp`: same canvas, transparent background.
- `mid_world.webp`: same canvas, transparent background.
- `foreground.webp`: same canvas, transparent background.

Do not crop each layer to visible pixels. The shared full canvas is intentional.

### Tavern

- `background.webp`: 960x540 or exact integer multiple, opaque.
- `foreground.webp`: same canvas, transparent background, optional.

### Characters / props

Transparent WebP with tight-but-safe padding:

- `player.webp`: recommended 128x192 source canvas; feet centered horizontally; foot baseline at 90-95% of image height.
- `oren.webp`: recommended 160x220 source canvas; same foot-baseline convention.
- `firewood.webp`: recommended 96x64 source canvas; object visually centered.

Exact raster resolution may be larger for quality, but aspect ratio and anchor convention must remain stable.

## Gameplay anchors that art must respect

The greybox currently proves these interaction regions. Art should visually place the corresponding objects around these screen-space positions rather than forcing gameplay code to chase decorative composition.

### Village

- player start: approximately `(430, 455)`;
- tavern interaction focal point / door: approximately `(825, 250)`;
- firewood strip: approximately `x=112..260`, `y=428..449`;
- well visual landmark: approximately `(485, 360)`;
- workshop landmark: left side around `(230, 264)`.

The tavern building may be larger than the interaction point, but its usable entrance must read clearly near the validated door position.

### Tavern

- player entry: approximately `(270, 425)`;
- Oren focal point: approximately `(650, 325)`;
- exit focal point: approximately `(110, 420)`.

## Collision readability

The player must visually understand why a blocked area is blocked.

Do not put an apparently walkable empty road under a collision rectangle. Conversely, decorative foreground objects must not imply collision unless the gameplay collision map actually blocks them.

During the first production-art pass we preserve current collision geometry unless the screenshot review demonstrates a concrete readability mismatch.

## Locked palette / style constraints

Keep the existing production canon:

- 2.5D physical cardboard theatre / handcrafted diorama in foreground/gameplay;
- realistic atmospheric distant natural world and volumetric sky;
- milk/marble + graphite dominant structure;
- visible signature turquoise, especially sky/water/accent surfaces;
- scarlet + black as restrained cultural accents;
- amber only for warmth, fire and selected metal/light;
- Udmurt + Armenian motifs dosage-controlled;
- large readable silhouettes;
- low micro-detail density;
- no neural-detail scatter;
- no generic dominant brown/beige/green medieval grading.

## Asset QA before handoff

Each export must pass:

1. no accidental text, pseudo-text, signatures or watermarks;
2. no broken architecture or duplicated structural elements;
3. no mutated hands/faces on player/Oren cutouts;
4. no floating flora/props or impossible intersections;
5. transparent files have genuinely transparent backgrounds;
6. object silhouette remains readable at gameplay scale;
7. dominant colors remain inside the locked palette;
8. scene still reads with few large forms, not hundreds of tiny decorations.

## Integration acceptance

After files are committed, Game Core will:

1. keep manifest status `awaiting_assets` while the pack is incomplete;
2. commit all required exports at the stable paths;
3. switch manifest status to `ready`;
4. preload production assets while keeping authoritative interaction coordinates unchanged;
5. run TypeScript/Vite build;
6. run full Python suite;
7. run the real Chromium critical route;
8. inspect four evidence screenshots: start, quest offer, completion, reload;
9. adjust only presentation/collision mismatches proven by those screenshots;
10. keep greybox fallback available until the production pass is accepted.

## Definition of handoff-ready

Visual Production is ready for integration when all required P0 files exist at the paths above, the village/tavern full-scene layers share exact canvas alignment, and the manifest can safely be moved from `awaiting_assets` to `ready`.
