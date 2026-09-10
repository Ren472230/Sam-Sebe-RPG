# Human Playtest Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current technically green prototype into a reliable second human-playtest candidate by removing the first-run setup trap, making NPC interaction spatially coherent, and making the playtest report prove whether NPC replies used the neural provider or fallback.

**Architecture:** Preserve the existing FastAPI + SQLite authority and Phaser presentation split. All changes stay inside the existing launcher, scene/input layer, dialogue UI, and canonical playtest reporting system. No new game truth, no new engine, no changes to `main`.

**Tech Stack:** Python 3.12+, FastAPI, SQLite, TypeScript, Phaser 3.90, Vite, Playwright, PowerShell/Windows BAT.

**Spec:** `Ультимативный промпт циклического совершенствования «Сам-себе-RPG».md` plus the real human report `sam-sebe-rpg-playtest-playtest-5c32db7c-4ca1-4204-8370-11cb77aae24b.md` and direct player feedback from 2026-09-09.

## Global Constraints

- Work only on `autotest/world-ready-2026-09-08`; never merge or modify `main` without explicit owner approval.
- Keep deterministic server state authoritative; the language model remains a language layer only.
- Use existing reporting/event systems rather than creating a parallel telemetry truth.
- Keep the coherent prototype visual fallback until the production scene is complete.
- One cycle = one primary hypothesis; every accepted cycle must pass all mandatory repository gates.
- Do not claim Human Experience Gate success without a fresh real human session.

---

### Task 1: Freeze the real-human P0 fixes as the new technical baseline

**Files:**
- Modify: `RUN_STATE.json`
- Modify: `CHAMPION_STATE.json`
- Modify: `AUTONOMOUS_LEARNING.md`

**Interfaces:**
- Consumes: branch head after the real-human stabilization changes.
- Produces: cycle 12 champion metadata and an explicit next constraint.

- [ ] **Step 1: Verify all six mandatory workflows on the current head.**

Expected: Visual Forge, Stream Slice, Prototype Web CI, Playable Candidate, Windows Compatibility, Living World Integration all `success`.

- [ ] **Step 2: Record cycle 12 as accepted only if the six gates are green.**

Record the real-human evidence: repeated dialogue opens, `S/ы` key capture, ghost talk buttons, duplicate actions, and misleading reload semantics.

- [ ] **Step 3: Set the next main constraint to first-run launch reliability.**

The owner had to manually run `pip install -e ".[dev]"` and `npm install` after `ModuleNotFoundError: samseberpg`; a double-click playtest launcher must bootstrap a fresh ZIP checkout.

### Task 2: Make the Windows playtest launcher actually one-click on a fresh ZIP

**Files:**
- Modify: `RUN_STREAM_SLICE.ps1`
- Modify: `PLAY_SAM_SEBE_RPG.bat`
- Modify: `tests/test_release_runbook.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `RUN_STREAM_SLICE.ps1 -Reset -PromptForOpenAIKey`.
- Produces: idempotent bootstrap for Python package + web dependencies and a server window that remains visible on startup failure.

- [ ] **Step 1: Write a failing launcher contract.**

Require the runner to contain checks equivalent to:

```powershell
python -c "import samseberpg"
python -m pip install -e ".[dev]"
Test-Path "web/node_modules"
npm install --no-audit --no-fund
```

Require the BAT launcher to use `powershell.exe -NoExit` so startup errors remain readable.

- [ ] **Step 2: Run the narrow Python test and verify RED.**

Run: `python -m pytest -q tests/test_release_runbook.py`

- [ ] **Step 3: Implement idempotent bootstrap.**

Behavior:
- fail fast with a readable message if `python` is unavailable;
- install the editable Python package only when `import samseberpg` fails;
- fail fast with a readable message if `npm` is unavailable;
- run `npm install --no-audit --no-fund` only when `web/node_modules` is absent;
- keep the OpenAI key in-process only;
- keep the PowerShell window open if startup fails.

- [ ] **Step 4: Verify GREEN and Windows compatibility.**

Run narrow tests first, then mandatory Windows gate.

### Task 3: Replace ghost/global NPC talk actions with spatial interaction

**Files:**
- Modify: `web/src/main.ts`
- Modify: `web/src/scenes/VillageScene.ts`
- Modify: `web/src/scenes/TavernScene.ts`
- Modify: `web/tests/living-npc-contract.test.ts`
- Modify: `web/tests/00-first-run-clarity.spec.ts`

**Interfaces:**
- Consumes: authoritative `snapshot.world.visible_actors` and scene-rendered NPC positions.
- Produces: `E` / touch interaction only when the player is physically near a rendered NPC.

- [ ] **Step 1: Write RED tests.**

Require normal mode to expose no global `Поговорить: ...` buttons. Require VillageScene to derive a nearest rendered NPC and open `dialogue.openNpc(actorId)` from the contextual interaction. Add a real Chromium check that approaches Mira, sees `поговорить с Мирой`, presses `E`, and opens the Mira dialogue.

- [ ] **Step 2: Remove the global talk-button loop from `bindWorldPulse`.**

Keep World Pulse observational and keep existing wait/move/resource controls unchanged for this cycle.

- [ ] **Step 3: Add spatial NPC interaction in VillageScene.**

Use the same authoritative `visible_actors` that are already rendered. Interaction payload:

```ts
type VillageInteraction =
  | { kind: "firewood"; item: Hotspot }
  | { kind: "tavern" }
  | { kind: "npc"; actorId: string; name: string };
```

On `kind === "npc"`, call `getRuntime().dialogue.openNpc(actorId)`.

- [ ] **Step 4: Materialize any additional visible tavern NPCs.**

Keep Oren's current production/fallback representation, but render the visible wayfarer/Talen when authoritative state says he is present so `Рядом: Тален` is visually truthful.

- [ ] **Step 5: Run contract + browser tests.**

Run: `npm run test:contract`, `npm run build`, `npm run test:e2e`.

### Task 4: Make neural/fallback dialogue observable in the existing playtest report

**Files:**
- Modify: `web/src/ui/DialoguePanel.ts`
- Modify: `web/src/playtest.ts`
- Modify: `web/src/playtestClient.ts`
- Modify: `src/samseberpg/playtest.py`
- Modify: `tests/test_playtest_report.py`
- Modify: `web/tests/living-npc-contract.test.ts`

**Interfaces:**
- Consumes: existing `DialogueDecision.used_fallback`.
- Produces: a narrow `DIALOGUE_RESULT` playtest event with `npc_id` and `used_fallback`; report aggregates neural/fallback response counts without logging dialogue text.

- [ ] **Step 1: Write RED report and client-contract tests.**

Expected report section:

```text
## DIALOGUE
Responses observed: N
Neural responses: X
Fallback responses: Y
```

No player/NPC message body is stored in telemetry.

- [ ] **Step 2: Dispatch a browser event after every successful NPC reply.**

Payload contains only `npc_id` and `used_fallback`.

- [ ] **Step 3: Record the event through the existing playtest client endpoint.**

Add `DIALOGUE_RESULT` to the existing allowed event type set; do not create a second reporting backend.

- [ ] **Step 4: Aggregate the event in `PlaytestService.report`.**

The report must distinguish neural from fallback replies and keep the existing PASS/FAIL route semantics unchanged.

- [ ] **Step 5: Run Python + web contract tests.**

Run: `python -m pytest -q tests`, `npm run test:contract`.

### Task 5: Full regression gate and handoff to a second human session

**Files:**
- Modify: `RUN_STATE.json`
- Modify: `CHAMPION_STATE.json`
- Modify: `AUTONOMOUS_LEARNING.md`
- Modify: PR #47 body

**Interfaces:**
- Consumes: accepted cycle SHAs and mandatory workflow run IDs.
- Produces: a single current champion with honest remaining limits.

- [ ] **Step 1: Run all mandatory gates on the final head.**

Required: six workflow families all `success`, including real Chromium and Windows.

- [ ] **Step 2: Review failures instead of weakening assertions.**

If a new browser failure exposes a real interaction regression, fix the product and rerun. Do not increase timeouts or relax invariants merely to get green.

- [ ] **Step 3: Update autonomous state and learning log.**

Set phase to `ready_for_second_human_experience_gate` only after all mandatory gates are green.

- [ ] **Step 4: Keep PR #47 draft and `main` untouched.**

The next human test should focus on: fresh ZIP launch, Russian free text including `ы`, one press = one interaction, physically visible NPCs, actual neural/fallback report counts, page reload persistence, and overall clarity/desire to continue.
