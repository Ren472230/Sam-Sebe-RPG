# Start Village production asset mapping

Date: 2026-08-26
Base main: `ecdd796e5a425d77f7911b5293588ed496b4f619`
Purpose: integration-time truth for the 14 locked Start Village slots.

## Status semantics

- `FOUND` means project history or a recovered historical container proves the canonical raw existed. It does **not** mean the bytes are mounted in this integration runtime.
- `NOT ACCESSIBLE` means the asset is recovered/identified by evidence but raw bytes are not available to the current integration runtime. It is **not** `MISSING`.
- No historical candidate is promoted to a runtime role merely because it looks plausible.
- No source image may be edited in this branch. Runtime composites/resizes must remain derived artifacts with source mapping.

Current integration runtime raw-byte access: **0/14**.
Historical materialization evidence: **4/14 physical and technically valid** (`BUSH_001`, `GRASS_MASS_001`, `FOREGROUND_FLORA_001`, `NPC_002`).
Proven missing: **0/14**.

| Canonical ID | Access state | Canonical mapping / best evidence | Dimensions | RGBA / alpha | Visual QA / mapping state | Source | Intended runtime layer |
|---|---|---|---|---|---|---|---|
| `SKY_001.png` | NOT ACCESSIBLE | `Бирюзовое небо над туманными горами.png` + old canonical history | unknown | unknown | CANDIDATE; exact separability/pixel QA pending | File Library + production history | L0 SKY |
| `DISTANT_MOUNTAINS_001.png` | NOT ACCESSIBLE | `Бирюзовая панорама снежных гор.png` + nearby old mountain variants | unknown | unknown | CANDIDATE; separability review required | File Library + production history | L1 DISTANT NATURE |
| `DISTANT_FOREST_001.png` | NOT ACCESSIBLE | `Туманные горные леса на прозрачном фоне.png` | unknown | transparency implied by recovered description; not technically verified | STRONG CANDIDATE | File Library | L1 DISTANT NATURE |
| `MID_NATURE_001.png` | NOT ACCESSIBLE | historical locked canonical; exact raw ref unresolved | unknown | unknown | HISTORY-RECOVERED / LOCKED evidence; raw QA pending | production docs/boards | L2 MID NATURE |
| `GROUND_PATH_001.png` | NOT ACCESSIBLE | `Каменная тропа на прозрачном фоне.png` | unknown | transparency implied by recovered title; not technically verified | STRONG CANDIDATE | File Library | L4 GAMEPLAY |
| `TAVERN_001.png` | NOT ACCESSIBLE | historical locked exterior tavern; exact isolated raw ref unresolved | unknown | unknown | HISTORY-RECOVERED; **not** an interior mapping | production docs/boards | L3 ARCHITECTURE only; never TavernScene interior |
| `HOUSE_002.png` | NOT ACCESSIBLE | `Фэнтезийный каменный дом с верандой.png` | unknown | recovered description says isolated/checkerboard; not technically verified | STRONG CANDIDATE | File Library | L3 ARCHITECTURE |
| `WORKSHOP_001.png` | NOT ACCESSIBLE | `Мраморная кузница с открытой мастерской.png` | unknown | recovered description says isolated transparent; not technically verified | ACCEPT mapping; raw technical QA pending | File Library | L3 ARCHITECTURE |
| `WELL_001.png` | NOT ACCESSIBLE | `Мраморный колодец с бирюзовой водой.png` | unknown | recovered description says clean transparent cutout; not technically verified | ACCEPT mapping; raw technical QA pending | File Library | L4 GAMEPLAY |
| `BUSH_001.png` | FOUND historically; bytes NOT ACCESSIBLE here | exact canonical raw from historical flora/NPC ZIP | 1254x1254 | PNG / RGBA / alpha 0-255 | 23/24, LOCKED, technical OK | `START_VILLAGE_FLORA_NPC_BLOCK_v1(2).zip` | L4 GAMEPLAY |
| `GRASS_MASS_001.png` | FOUND historically; bytes NOT ACCESSIBLE here | exact canonical raw from historical flora/NPC ZIP | 1254x1254 | PNG / RGBA / alpha 0-255 | 23/24, LOCKED, technical OK | `START_VILLAGE_FLORA_NPC_BLOCK_v1(2).zip` | L4 GAMEPLAY |
| `FOREGROUND_FLORA_001.png` | FOUND historically; bytes NOT ACCESSIBLE here | exact canonical raw from historical flora/NPC ZIP | 1254x1254 | PNG / RGBA / alpha 0-255 | 22/24, LOCKED, technical OK | `START_VILLAGE_FLORA_NPC_BLOCK_v1(2).zip` | L5 FOREGROUND |
| `NPC_MASTER_001.png` | NOT ACCESSIBLE | `Женщина в народном наряде с вышивкой.png` + locked master boards | unknown | unknown | STRONG CANDIDATE; runtime identity mapping unproven | File Library + master boards | L4 GAMEPLAY NPC; no player/Oren assignment |
| `NPC_002.png` | FOUND historically; bytes NOT ACCESSIBLE here | exact canonical raw from historical flora/NPC ZIP / elder-man turnaround evidence | 1024x1536 | PNG / RGBA / alpha 0-254 | 22/24, LOCKED, technical OK | `START_VILLAGE_FLORA_NPC_BLOCK_v1(2).zip` | L4 GAMEPLAY NPC; no player/Oren assignment |

## Historical parallax contract

Recovered `START_VILLAGE_PARALLAX_TEST_v1(2).zip` passed its unit test with the following motion coefficients:

- L0 SKY: `0.005`
- L1 DISTANT NATURE: `0.045`
- L2 MID NATURE: `0.16`
- L3 ARCHITECTURE: `0.43`
- L4 GAMEPLAY: `1.0`
- L5 FOREGROUND: `1.4`

The web runtime now preserves these exact coefficients in code and manifest metadata. Parallax remains disabled in the checked-in manifest until real derivatives have safe overscan and hotspot alignment can be validated in a browser. This prevents seams or interaction drift from being introduced without the source pixels.

## Runtime derivative drop-in contract

After the canonical raw bytes are materialized and visually approved, build derived 960x540-compatible production layers under `web/public/assets/production/village/` and fill the v2 manifest slots:

- `sky` -> L0 derivative
- `distant_nature` -> L1 derivative combining only approved distant mountains/forest sources
- `mid_nature` -> L2 derivative
- `architecture` -> L3 derivative from approved Tavern/House/Workshop placement
- `gameplay` -> L4 derivative from approved ground/path/well/flora/NPC placement that matches gameplay anchors
- `foreground` -> optional L5 derivative

Do not enable Village production until the five core derivative slots (L0-L4) are materialized and loaded. Tavern/player/Oren/firewood slots are independent and may remain on their existing gameplay fallbacks.

## Explicit non-mappings

- `TAVERN_001.png` exterior is **not** `TavernScene` interior.
- `NPC_MASTER_001.png` is **not** automatically the player or Oren.
- `NPC_002.png` is **not** automatically the player or Oren.
- No production firewood raw is proven in this canonical 14-set; keep the existing backend-entity fallback until an approved prop exists.
