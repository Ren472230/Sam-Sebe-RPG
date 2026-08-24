# P0 Production Integration Status

Date: 2026-08-24

## Verified

- Gameplay vertical slice: Python suite, TypeScript/Vite build and full real Chromium critical route.
- Production-art runtime: implemented in `web/src/productionArt.ts`.
- Stable manifest: `web/public/assets/production/manifest.json`.
- Greybox fallback: active and browser-verified while manifest is `awaiting_assets`.
- Scene/gameplay anchors remain authoritative and unchanged by art mode.
- Frame-stall movement tunneling discovered during art-runtime acceptance was fixed by capping the village movement timestep; the original Chromium route passed after the fix.

## Current blocker

Final production WebP exports are not in the repository yet. `web/public/assets/production/` currently contains only `manifest.json`.

## Exact next action

1. Commit required Visual Production files to the manifest paths.
2. Keep optional foreground/UI files optional for first pass.
3. Switch manifest `status` from `awaiting_assets` to `ready`.
4. Run Python + TypeScript/Vite + real Chromium acceptance.
5. Inspect start / Oren offer / completion / reload screenshots.
6. Run a short human smoke test.
7. Merge PR #6 only after the production-art pass is accepted.
