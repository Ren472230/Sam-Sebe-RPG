# Start Village production asset mapping

Date: 2026-08-26
Base main: `ecdd796e5a425d77f7911b5293588ed496b4f619`
Purpose: integration-time truth for the 14 locked Start Village slots.

## Status semantics

- `FOUND` means the latest recovery evidence proves a physically usable canonical raw or an explicitly non-generative recovery derivative exists somewhere in the recovered project materials. It does **not** mean the bytes are mounted in this integration runtime.
- `NOT ACCESSIBLE` means the canonical slot exists historically or has a recovered candidate/mapping, but usable bytes are not available to the current integration runtime. It is **not** proof that the canonical asset never existed.
- `TECHNICAL PASS` is used only where the recovered evidence explicitly reports PNG/RGBA/dimensions/alpha validation. Do not infer it from a title, thumbnail, or historical lock.
- No historical candidate is promoted to a runtime role merely because it looks plausible.
- No source image may be edited in this branch. Runtime composites/resizes must remain derived artifacts with source mapping.

## Latest recovery checkpoint

The newest recovered visual checkpoint found for 2026-08-26 is `GAP_REPORT.md`, later than `START_VILLAGE_RECOVERY_LEDGER_v3.md`.

- Canonical slots confirmed by project history: **14/14**.
- Latest recovery reports physically usable without new image generation: **7/14**.
- Explicit technical PNG/RGBA validation available in recovered evidence: **4/14**.
- Current integration runtime raw-byte access: **0/14**.
- Image generation performed by this branch: **0**.

The seven physically usable recoveries are:

1. `SKY_001.png` — provisional MVP alias from `SKY_001_CURRENT.png`; L0 does not require alpha.
2. `HOUSE_002.png` — non-generative background isolation from locked `HOUSE_MASTER_001` reference.
3. `NPC_MASTER_001.png` — non-generative background isolation from locked `NPC_MASTER_001_BASE` reference.
4. `BUSH_001.png` — exact recovered raw.
5. `GRASS_MASS_001.png` — exact recovered raw.
6. `FOREGROUND_FLORA_001.png` — exact recovered raw.
7. `NPC_002.png` — exact recovered raw.

The latest exhaustive recovery still has seven unresolved physical materialization gaps: `DISTANT_MOUNTAINS_001`, `DISTANT_FOREST_001`, `MID_NATURE_001`, `GROUND_PATH_001`, `TAVERN_001`, `WORKSHOP_001`, `WELL_001`.

## Canonical 14-set inventory

| Canonical ID | Access state | Canonical mapping / best evidence | Dimensions | RGBA / alpha | Visual QA / mapping state | Source | Intended runtime layer |
|---|---|---|---|---|---|---|---|
| `SKY_001.png` | FOUND in latest recovery; bytes NOT ACCESSIBLE here | provisional MVP alias from `SKY_001_CURRENT.png` | unknown in mounted runtime | alpha not required for L0; no explicit technical alpha report in available checkpoint | PHYSICALLY USABLE recovery alias; keep provenance explicit | latest `GAP_REPORT.md` / recovered reference material | L0 SKY |
| `DISTANT_MOUNTAINS_001.png` | NOT ACCESSIBLE | historical references exist; older `Бирюзовая панорама снежных гор.png` family is not accepted as an independent production raw after exhaustive recovery | unknown | unknown | MATERIALIZATION GAP; do not promote baked sky/valley/forest candidate | latest `GAP_REPORT.md` + earlier File Library history | L1 DISTANT NATURE |
| `DISTANT_FOREST_001.png` | NOT ACCESSIBLE | historical `Туманные горные леса на прозрачном фоне.png` reference exists, but no accepted physical production raw is materialized | unknown | unknown | MATERIALIZATION GAP; independent forest layer still required | latest `GAP_REPORT.md` + earlier File Library history | L1 DISTANT NATURE |
| `MID_NATURE_001.png` | NOT ACCESSIBLE | explicitly LOCKED in old production docs; exact physical raw unresolved | unknown | unknown | MATERIALIZATION GAP; composites are not accepted as L2 | latest `GAP_REPORT.md` + production docs/boards | L2 MID NATURE |
| `GROUND_PATH_001.png` | NOT ACCESSIBLE | historical `Каменная тропа на прозрачном фоне.png` candidate identified, but raw bytes were never materialized | unknown | unknown | MATERIALIZATION GAP | latest `GAP_REPORT.md` + File Library history | L4 GAMEPLAY |
| `TAVERN_001.png` | NOT ACCESSIBLE | historical locked exterior tavern evidence; no proven isolated production raw materialized | unknown | unknown | MATERIALIZATION GAP; exterior only and **never** TavernScene interior | latest `GAP_REPORT.md` + production docs/boards | L3 ARCHITECTURE only |
| `HOUSE_002.png` | FOUND in latest recovery; bytes NOT ACCESSIBLE here | non-generative background isolation from locked `HOUSE_MASTER_001` reference | unknown in current evidence | unknown in current evidence | PHYSICALLY USABLE recovery derivative from locked source; exact technical PNG details not exposed in current checkpoint | latest `GAP_REPORT.md` / locked `HOUSE_MASTER_001` reference | L3 ARCHITECTURE |
| `WORKSHOP_001.png` | NOT ACCESSIBLE | `Мраморная кузница с открытой мастерской.png` had strong/accepted identity mapping, but usable raw bytes remain unavailable | unknown | unknown | MATERIALIZATION GAP despite accepted identity mapping | latest `GAP_REPORT.md` + earlier File Library recovery | L3 ARCHITECTURE |
| `WELL_001.png` | NOT ACCESSIBLE | `Мраморный колодец с бирюзовой водой.png` had strong/accepted identity mapping, but usable raw bytes remain unavailable | unknown | unknown | MATERIALIZATION GAP despite accepted identity mapping | latest `GAP_REPORT.md` + earlier File Library recovery | L4 GAMEPLAY |
| `BUSH_001.png` | FOUND historically; bytes NOT ACCESSIBLE here | exact canonical raw from historical flora/NPC ZIP | 1254x1254 | PNG / RGBA / alpha 0-255 | 23/24, LOCKED, TECHNICAL PASS | `START_VILLAGE_FLORA_NPC_BLOCK_v1(2).zip` / ledger v3 | L4 GAMEPLAY |
| `GRASS_MASS_001.png` | FOUND historically; bytes NOT ACCESSIBLE here | exact canonical raw from historical flora/NPC ZIP | 1254x1254 | PNG / RGBA / alpha 0-255 | 23/24, LOCKED, TECHNICAL PASS | `START_VILLAGE_FLORA_NPC_BLOCK_v1(2).zip` / ledger v3 | L4 GAMEPLAY |
| `FOREGROUND_FLORA_001.png` | FOUND historically; bytes NOT ACCESSIBLE here | exact canonical raw from historical flora/NPC ZIP | 1254x1254 | PNG / RGBA / alpha 0-255 | 22/24, LOCKED, TECHNICAL PASS | `START_VILLAGE_FLORA_NPC_BLOCK_v1(2).zip` / ledger v3 | L5 FOREGROUND |
| `NPC_MASTER_001.png` | FOUND in latest recovery; bytes NOT ACCESSIBLE here | non-generative background isolation from locked `NPC_MASTER_001_BASE` reference | unknown in current evidence | unknown in current evidence | PHYSICALLY USABLE recovery derivative; runtime identity mapping remains unproven | latest `GAP_REPORT.md` / locked master reference | L4 GAMEPLAY NPC; no player/Oren assignment |
| `NPC_002.png` | FOUND historically; bytes NOT ACCESSIBLE here | exact canonical raw from historical flora/NPC ZIP / elder-man turnaround evidence | 1024x1536 | PNG / RGBA / alpha 0-254 | 22/24, LOCKED, TECHNICAL PASS | `START_VILLAGE_FLORA_NPC_BLOCK_v1(2).zip` / ledger v3 | L4 GAMEPLAY NPC; no player/Oren assignment |

## Historical parallax contract

Recovered `START_VILLAGE_PARALLAX_TEST_v1(2).zip` passed its unit test with the following motion coefficients:

- L0 SKY: `0.005`
- L1 DISTANT NATURE: `0.045`
- L2 MID NATURE: `0.16`
- L3 ARCHITECTURE: `0.43`
- L4 GAMEPLAY: `1.0`
- L5 FOREGROUND: `1.4`

The web runtime preserves these exact coefficients in code and manifest metadata. Parallax remains disabled in the checked-in manifest until real derivatives have safe horizontal overscan and hotspot alignment can be validated in a real browser. This prevents seams, black edges, or interaction drift from being introduced without the source pixels.

## Runtime derivative drop-in contract

After the canonical bytes/recovery derivatives are mounted and visually approved, build 960x540-compatible runtime derivatives under `web/public/assets/production/village/` and fill the v2 manifest slots:

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
