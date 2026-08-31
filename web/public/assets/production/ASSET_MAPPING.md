# Start Village production asset mapping

Date: 2026-08-26
Base main: `ecdd796e5a425d77f7911b5293588ed496b4f619`
Branch: `dev/production-visual-integration`
Purpose: factual materialization + canonical mapping ledger for the 14 locked Start Village production slots.

## Status semantics

- `RAW PHYSICAL NOW` means bytes were actually opened from the attachments mounted for this integration pass. It does not by itself prove canonical identity.
- `TECHNICAL PASS` separates PNG integrity from canonical/runtime suitability. A valid PNG can still fail an isolated-layer requirement.
- `ACCEPT` means current pixel QA plus historical recovery evidence is strong enough to use the mapping without inventing identity.
- `CANDIDATE / NOT USED` means the bytes are preserved as evidence but are not promoted into a canonical runtime slot.
- `UNMATERIALIZED` is not `MISSING`.
- Source PNGs are not retouched. Runtime L3/L4 files are resize/composite derivatives with explicit source mapping.

## Attachment-level technical QA

| Recovered identity | PNG | Dimensions | Mode / alpha | Pixel QA | SHA-256 |
|---|---|---:|---|---|---|
| Elder-man turnaround -> `NPC_002` | PASS | 1224x1285 | RGBA, alpha 0-255 | isolated multi-pose sheet; transparent corners | `a8a5151d888aed48a64f1f388e54822cf90d39b5c44629c91c5abc0a46a3b737` |
| Woman folk-costume -> `NPC_MASTER_001` candidate | PASS | 1086x1448 | RGBA but alpha 255-255 | baked cream background; fails isolated-cutout requirement | `d3d02c001b74f38e3c034ead99a07562235f14ee0f84448b821b5a140aa228e8` |
| Turquoise sky + misty mountains -> `SKY_001` candidate | PASS | 1672x941 | RGBA but alpha 255-255 | full opaque scene; mountain mass is baked into L0 candidate | `de31862437eb88be76e14b88ee6c84898d4bb423913ddb6323fad043fd4a4c4c` |
| Misty forest + mountain ridge -> `DISTANT_FOREST_001` candidate | PASS | 1672x941 | RGBA, alpha 0-255 | transparent cutout but large mountain ridge is baked with forest | `056f728a9d826bb4dcbd04aace8817ebd59bc0fa003d9a7c74909a860fba054a` |
| Stone path -> `GROUND_PATH_001` | PASS | 1672x941 | RGBA, alpha 0-255 | isolated gameplay path; no baked full environment | `742b5afddc0a4575cc024a50e69908e24aa4b63f7a57990c577758427b578b39` |
| Pale-stone house -> `HOUSE_002` | PASS | 1536x1024 | RGBA, alpha 0-254 | isolated architecture; clean cutout; family match | `3aedc68e05a9c0fa1c0dd7b15ac5de60435e621bf77f4ad35a370ee42ff5ae44` |
| Marble well -> `WELL_001` | PASS | 1536x1024 | RGBA, alpha 0-254 | isolated well; marble/graphite/turquoise/red textile match | `8a3bc2976203a0cd9e6fd9e774cd65cfa3b51a3fd59da55e621b0d312ff07d46` |
| Open marble workshop -> `WORKSHOP_001` | PASS | 1536x1024 | RGBA, alpha 0-254 | isolated workshop; open forge/workspace matches historical ACCEPT description | `094ef7cc029eb0b93d162b94f5af66a97692d6e893b3a937ef0258ae6c7ebab0` |

## Canonical 14-set ledger

| Canonical ID | Raw physical now | Technical PASS | Mapping | Runtime |
|---|---|---|---|---|
| `SKY_001.png` | YES - candidate bytes | PNG PASS; L0 separability FAIL | CANDIDATE; **not promoted** because mountains are baked into the sky image | NOT USED; greybox sky remains |
| `DISTANT_MOUNTAINS_001.png` | NO | historical only | UNMATERIALIZED | FALLBACK |
| `DISTANT_FOREST_001.png` | YES - candidate bytes | PNG/alpha PASS; independent-layer separability FAIL | STRONG CANDIDATE rejected from canonical promotion because a large mountain ridge is baked with the forest | NOT USED |
| `MID_NATURE_001.png` | NO | historical only | UNMATERIALIZED | FALLBACK |
| `GROUND_PATH_001.png` | YES | PASS | ACCEPT | PROD derivative in L4 |
| `TAVERN_001.png` | NO | historical only | UNMATERIALIZED exterior slot; never TavernScene interior | exterior FALLBACK / TavernScene GREYBOX |
| `HOUSE_002.png` | YES | PASS | ACCEPT | PROD derivative in L3 |
| `WORKSHOP_001.png` | YES | PASS | ACCEPT | PROD derivative in L3 |
| `WELL_001.png` | YES | PASS | ACCEPT | PROD derivative in L4 |
| `BUSH_001.png` | NO in this runtime | historical PASS: 1254x1254 RGBA alpha 0-255, QA 23/24 | ACCEPT / LOCKED historically; bytes currently UNMATERIALIZED | FALLBACK |
| `GRASS_MASS_001.png` | NO in this runtime | historical PASS: 1254x1254 RGBA alpha 0-255, QA 23/24 | ACCEPT / LOCKED historically; bytes currently UNMATERIALIZED | FALLBACK |
| `FOREGROUND_FLORA_001.png` | NO in this runtime | historical PASS: 1254x1254 RGBA alpha 0-255, QA 22/24 | ACCEPT / LOCKED historically; bytes currently UNMATERIALIZED | FALLBACK |
| `NPC_MASTER_001.png` | YES - candidate bytes | PNG PASS; isolated-alpha FAIL | CANDIDATE; baked background prevents canonical runtime promotion in this branch | NOT USED |
| `NPC_002.png` | YES | PASS for attached PNG; 1224x1285 RGBA alpha 0-255 | ACCEPT visual identity: uploaded sheet matches recovered elder-man turnaround description. Historical ZIP raw was reported as 1024x1536, so byte identity with that older raw is **not claimed** | RAW inspected in current session; no player/Oren/runtime-role assignment |

Current physical attachments: **8/14 slots have candidate or accepted bytes in this runtime**.
Current accepted mappings from these attachments: **5** (`GROUND_PATH_001`, `HOUSE_002`, `WORKSHOP_001`, `WELL_001`, `NPC_002`).
Current runtime visual integration uses **4 accepted scene assets**; `NPC_002` has no proven gameplay role and therefore is not rendered.
Proven missing canonical assets: **0**.

## Runtime derivatives

The source composition is authored on the 960x540 target canvas, then encoded to smaller transparent WebP shipping derivatives to keep this PR lightweight. Phaser displays every layer at 960x540. This is a derived runtime export only; the attached source PNGs are unchanged.

### `village/L3_ARCHITECTURE_PARTIAL.webp`

- Shipping derivative: **400x225 WebP**, 11,048 bytes, transparent, Git blob `d65e6d1b2d96d1e73535753b40dfa931d30e6057`.
- Source composition: transparent 960x540 derivative from:
  - `WORKSHOP_001`: resized to 350px wide on the 960x540 composition, centered on x=230 with bottom y=335. This aligns with the existing Workshop presentation anchor and stays above the canonical firewood strip.
  - `HOUSE_002`: resized to 265px wide on the 960x540 composition, centered on x=565 with bottom y=332.

No production Tavern exterior is inserted because `TAVERN_001` is not materialized. The existing Tavern entrance greybox remains the truthful interaction landmark.

### `village/L4_GAMEPLAY_PARTIAL.webp`

- Shipping derivative: **256x144 WebP**, 6,298 bytes, transparent, Git blob `8569e6b6204547d3618399c01f761b6ff777e47b`.
- Source composition: transparent 960x540 derivative from:
  - `GROUND_PATH_001`: proportional runtime resize to the 960x540 gameplay canvas.
  - `WELL_001`: resized to 165px wide on the 960x540 composition, centered at x=485 with bottom y=420, aligned with the existing well obstacle/presentation area.

Canonical firewood entities remain the existing gameplay fallback and are not painted into this layer.

## Partial production policy

The checked-in manifest is `status: partial` and activates only the materialized L3/L4 WebP derivatives. The runtime renders these transparent production layers above the readable greybox base. It does **not** synthesize absent L0/L1/L2/L5 slots.

Tavern interior, player, Oren and firewood production slots stay empty/fallback. `TAVERN_001` exterior is not reused as an interior, and neither NPC asset is assigned to player/Oren.

## Parallax

Historical coefficients remain locked:

- L0 SKY `0.005`
- L1 DISTANT NATURE `0.045`
- L2 MID NATURE `0.16`
- L3 ARCHITECTURE `0.43`
- L4 GAMEPLAY `1.0`
- L5 FOREGROUND `1.4`

Parallax remains **disabled** in this partial materialization. The current accepted L3/L4 source compositions have no safe horizontal overscan. Enabling camera-relative scroll factors would expose transparent/greybox seams and risk visual hotspot drift. Partial static production is therefore the truthful P0 result until seam-safe background/foreground layers are materialized.

## Remaining unresolved canonical slots after this pass

These canonical slots are still unresolved for production use; none are labeled `MISSING`:

- `SKY_001` - physical candidate exists but fails independent L0 separability.
- `DISTANT_MOUNTAINS_001` - UNMATERIALIZED.
- `DISTANT_FOREST_001` - physical candidate exists but fails independent forest-layer separability.
- `MID_NATURE_001` - UNMATERIALIZED.
- `TAVERN_001` - UNMATERIALIZED exterior.
- `BUSH_001` - historically validated, current bytes UNMATERIALIZED.
- `GRASS_MASS_001` - historically validated, current bytes UNMATERIALIZED.
- `FOREGROUND_FLORA_001` - historically validated, current bytes UNMATERIALIZED.
- `NPC_MASTER_001` - physical candidate exists but baked background prevents canonical cutout use.
