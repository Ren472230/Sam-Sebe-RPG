# Sunday Prototype Art Design

Date: 2026-08-28
Branch: `dev/production-visual-integration`
Target: playable vertical slice by Sunday, 2026-08-30

## Decision

For the Sunday prototype, stop treating the current production visual pipeline as a release blocker. Do not spend remaining critical-path time on generative layer decomposition, Visual Forge R&D, parallax completion, or the 14-asset production registry.

Use a coherent temporary prototype-art mode built from freely reusable CC0 RPG assets. The prototype must look like one game, remain readable, preserve all existing gameplay coordinates and logic, and be replaceable later without changing backend or quest behavior.

The production visual canon remains a post-prototype target and is not deleted or redefined by this downgrade.

## Goals

1. Produce a visually coherent Village scene and Tavern scene quickly.
2. Keep the current playable route, collision/hotspot coordinates, quest flow, persistence, API contract, and backend unchanged.
3. Remove image-generation uncertainty from the Sunday critical path.
4. Make prototype art replaceable by later production art through a narrow runtime seam.
5. Keep the visual branch honest: prototype assets must be labeled as prototype assets, never as canonical production assets.

## Non-goals for Sunday

- No unique final Armenian/Udmurt production visual identity.
- No neural scene reconstruction or inpainting pipeline.
- No Visual Forge layer editor expansion.
- No 14-production-asset completion requirement.
- No parallax requirement.
- No dynamic lighting requirement.
- No animated player requirement unless it is essentially free after the static version is working.
- No new camera system.
- No changes to backend, API, quest, inventory, persistence, relation logic, database schema, NPC simulation, or firewood logic.

## Source Art Policy

Primary source: Kenney CC0 RPG-style assets.

Preferred order:

1. One coherent Kenney pack for environment and props.
2. A compatible Kenney character pack only if the primary pack does not provide usable characters.
3. Do not mix unrelated visual families merely to fill space.

License rule: only assets with verified CC0/public-domain-style reuse terms may enter the Sunday prototype-art set. Store source attribution/license metadata in a small text or JSON file even when attribution is not legally required, so provenance remains auditable.

No paid image API is required.

## Runtime Architecture

Add a separate prototype-art path instead of mutating the production-art contract.

Expected runtime assets:

- `web/public/assets/prototype/village.png`
- `web/public/assets/prototype/tavern.png`
- `web/public/assets/prototype/player.png`
- `web/public/assets/prototype/oren.png`
- `web/public/assets/prototype/firewood.png`
- `web/public/assets/prototype/provenance.json`

The Village and Tavern are each a single precomposed 960x540 background image. Buildings, terrain, furniture, and non-interactive decoration may be baked into those backgrounds.

Interactive entities that must move, disappear, or remain independently addressable stay separate sprites: player, Oren, and firewood.

## Runtime Selection

Introduce one explicit runtime art mode with values equivalent to:

- `prototype`
- existing production/partial-production path
- existing greybox/fallback path

For the Sunday branch, `prototype` is the preferred visual mode when all required prototype files load successfully.

Fallback behavior remains deterministic:

1. If prototype art is complete and loadable, render prototype art.
2. Otherwise use the existing production/partial-production path when valid.
3. Otherwise use existing greybox/fallback rendering.

No silent failure and no false `production` label for prototype art.

Expose diagnostics through the existing `data-*` convention so browser tests can distinguish `prototype`, `partial-production`, and `greybox` states.

## Scene Composition Constraints

The backgrounds must respect existing gameplay geography rather than changing gameplay to fit the art.

Village composition must visually support the existing anchors/hotspots already used by the game, especially:

- player start around `[430, 455]`
- tavern door around `[825, 250]`
- well around `[485, 360]`
- workshop around `[230, 264]`
- firewood strip around `x=112..260`, `y=428..449`

Exact collision rectangles and interaction logic remain unchanged.

The background is decorative/readability support. If a decorative object conflicts with an existing interaction path, the art changes; gameplay coordinates do not.

Tavern composition must preserve the current Oren interaction route and exit geometry.

## Visual Quality Bar

Sunday prototype art is accepted when:

- the game reads immediately as a single coherent RPG visual style;
- Village and Tavern are visually complete backgrounds, not transparent partial cutouts;
- interactive objects are distinguishable from the background;
- there are no obvious stretched low-resolution composites like the rejected partial Start Village preview;
- no black/white alpha halos are visible at runtime scale;
- no decorative element visually blocks a required walk/interact path;
- UI remains readable over both backgrounds.

This is a coherence/readability gate, not a final-art gate.

## Implementation Boundaries

Keep the change visual/web-only.

Likely touched areas:

- `web/public/assets/prototype/**`
- runtime visual loader/renderer near `web/src/productionArt.ts` or a small adjacent module
- manifest/config selection for prototype mode
- contract/browser tests covering art mode and load/fallback behavior

Do not remove the current production-art implementation, Visual Forge code, registry, or production assets. They remain available for post-Sunday work.

## Testing Strategy

Use test-driven changes for runtime behavior.

Minimum automated gates:

1. Contract test: prototype mode is reported distinctly and does not masquerade as production.
2. Materialization test: every required prototype path exists and has non-trivial bytes.
3. Fallback test: a missing prototype asset falls back without breaking the scene.
4. Browser/vertical-slice smoke: the critical firewood route still works with prototype art enabled.
5. Build/typecheck remains green.

Visual QA:

- Capture Village and Tavern screenshots at runtime viewport.
- Verify anchors visually align with current interaction geography.
- Reject obvious stretching, clipping, haloing, or mismatched visual-family assets.

## Critical Path

1. Integrate a coherent CC0 prototype asset set.
2. Produce `village.png` and `tavern.png` at 960x540 around existing gameplay geography.
3. Add static player/Oren/firewood sprites.
4. Add runtime prototype-mode selection and fallback.
5. Run contract/build/browser checks.
6. Only if all above is green and time remains, improve decoration or character animation.

Everything else is deferred.

## Rollback

Prototype mode is isolated. Removing or disabling the prototype selection must restore the existing production/partial-production/greybox behavior without backend or gameplay migrations.

## Success Criterion

By Sunday, the current vertical slice is playable end-to-end and visually coherent enough to demonstrate without explaining away broken or incomplete art. The prototype art is explicitly temporary and can later be replaced by the locked production visual direction without rewriting game logic.