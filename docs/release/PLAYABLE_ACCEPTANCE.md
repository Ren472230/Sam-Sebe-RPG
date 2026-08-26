# Playable Vertical Slice — Release Acceptance

**Release deadline:** 2026-08-30 18:00  
**Internal playable gate:** 2026-08-28

Use this page on the release evening. P0 is only the route:

`village -> tavern -> Oren -> bring_5_firewood -> exact-once consequence -> restart -> same consequence`

## Prerequisites

- Python 3.12+
- Node.js 22+
- npm
- repository revision containing the backend vertical slice, Phaser client and DEV-3 acceptance assets
- no source edits are required to launch

OpenAI is optional. The route **must** remain completable when `OPENAI_API_KEY` is absent or invalid.

## Clean start

From repository root in Windows PowerShell:

```powershell
Remove-Item data\world.sqlite3 -ErrorAction SilentlyContinue
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python scripts\smoke_vertical_slice.py
```

Smoke must exit `0` and end with:

```text
[PASS] vertical slice backend smoke complete
```

Then run the authoritative acceptance test:

```powershell
pytest -q tests\test_vertical_slice_acceptance.py
```

## Start backend

Terminal 1, repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m samseberpg.server
```

Expected backend health:

`http://127.0.0.1:8000/api/health` -> `{"ok": true}`

## Start frontend

Terminal 2:

```powershell
cd web
npm install
npm run build
npm run dev
```

Open:

`http://127.0.0.1:5173`

Controls: `WASD` to move, `E` to interact, dialogue buttons for quest actions.

## Manual playthrough checklist

- [ ] Fresh save starts in the playable village area.
- [ ] Move to the village square.
- [ ] Enter the tavern.
- [ ] Approach Oren and open dialogue.
- [ ] Oren offers `bring_5_firewood`.
- [ ] Accept the quest; HUD/state shows active quest and `0/5` firewood.
- [ ] Leave the tavern and reach the workshop yard.
- [ ] Take four canonical firewood items; count becomes exactly `4/5`.
- [ ] Return to Oren; early turn-in is rejected and gives no coins/trust/memory.
- [ ] Return to the workshop and take the fifth canonical firewood; count becomes exactly `5/5`.
- [ ] Return to Oren and turn in once; quest becomes completed.
- [ ] Reward is granted exactly once; Oren trust increases and one persistent memory is created.
- [ ] Oren's post-quest dialogue is different and acknowledges the consequence.
- [ ] A second turn-in attempt is rejected and does not duplicate reward/trust/memory.
- [ ] Perform the full restart test below.

## Full restart test

1. Note current coins, Oren trust and completed quest state.
2. Stop the backend completely with `Ctrl+C`.
3. Close/reopen the game tab or leave it closed while the backend is down.
4. Start backend again with `python -m samseberpg.server` using the same `data/world.sqlite3`.
5. Reopen/refresh `http://127.0.0.1:5173`.
6. Confirm the same local player/session is restored.
7. Confirm the quest is still completed.
8. Confirm coins and Oren trust are unchanged from the completed state.
9. Talk to Oren: the persistent memory must still affect dialogue.
10. Try turn-in again: reward must not duplicate.

Any loss of player, completion, relation, memory or exact-once protection is **P0 NO-GO**.

## OpenAI-off fallback test

Stop backend. In the backend PowerShell terminal:

```powershell
Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
$env:SAM_SEBE_DB = "data/fallback-acceptance.sqlite3"
Remove-Item $env:SAM_SEBE_DB -ErrorAction SilentlyContinue
python -m samseberpg.server
```

Repeat the same critical route from a fresh player. Oren dialogue must be deterministic fallback, the quest must still be offered/accepted/completed, and restart persistence must still pass.

After the test, remove the override if desired:

```powershell
Remove-Item Env:SAM_SEBE_DB -ErrorAction SilentlyContinue
```

## GO / NO-GO gates

| Gate | PASS condition | NO-GO condition |
|---|---|---|
| 1 — Backend | `python scripts\smoke_vertical_slice.py` and Python acceptance pass; exact-once reward verified | loop, persistence, or duplicate protection fails |
| 2 — Client | `npm run build` passes; player moves; UI reaches Oren, accepts, collects and turns in | client/backend disconnect or quest cannot be completed through UI |
| 3 — Restart | same player, completed quest, relation and memory survive full backend restart | any canonical consequence is lost |
| 4 — No OpenAI | fresh fallback run completes the whole quest | dialogue provider failure blocks progression |
| 5 — Clean start | new user launches from these commands without source edits | manual code/database edits are required |

**Release GO requires all five gates PASS.** One P0 failure means NO-GO regardless of visual polish.

## Known P0 limitations that do not block release

- exactly one quest and one required NPC consequence;
- greybox/placeholder presentation is acceptable until production visual assets are dropped in;
- player pixel coordinates are presentation state and need not persist; canonical logical location must persist;
- no combat, crafting, multiplayer, procedural quests or large world simulation;
- OpenAI-enhanced dialogue is optional, never authoritative.

## 28 August risk rule

If by **2026-08-28** the greybox route

`start -> Oren -> quest -> 5 firewood -> completion -> consequence -> restart`

is not passing end-to-end through the real client, mark the release as a serious **NO-GO risk**. Do not downgrade that failure to UI polish.
