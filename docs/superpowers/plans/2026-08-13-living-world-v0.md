# Living World v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one deterministic autonomous NPC-to-NPC resource chain that runs from world ticks, shares authoritative state with player actions, persists in SQLite, and is observable in play.

**Architecture:** Add `LivingWorldService` for Mira/Kaspar autonomous rules. `DayService` processes each intermediate tick and invokes a callback; `GameService` wires Living World into every successful time-advancing action. Autonomous evidence uses separate `world_events`.

**Tech Stack:** Python 3.12+, sqlite3, pytest, standard library only.

## Global Constraints

- No LLM, GOAP, generic planner, utility AI, background worker, wall-clock catch-up, new NPC/location, economy, combat, hunger, or resource respawn.
- Exactly two autonomous NPCs: Mira and Kaspar.
- Exactly one shared resource chain: usable wood.
- `WAIT N` must equal N one-tick advances.
- Player and NPCs mutate the same resource/entity state.
- Autonomous `world_events` stay separate from player `action_events`.
- Existing first-day and Behavior Engine behavior must remain green.

---

### Task 1: Persistent autonomous state and events

**Files:** `src/samseberpg/db.py`, `tests/test_living_world.py`

- [ ] Write RED test: `world_events` exists; Mira has `wood_stock=2/work_cycles=0/requested_wood=false`; Kaspar `carrying_wood=0`; `driftwood_1` has `useful_wood`; event list starts empty.
- [ ] Run focused test and verify expected failure.
- [ ] Add schema/bootstrap and `GameDatabase.list_world_events()` decoding `data_json`.
- [ ] Run focused + full suite.

### Task 2: Intermediate tick semantics

**Files:** `src/samseberpg/day.py`, `tests/test_day.py`

- [ ] Write RED test that `DayService.advance(conn, 3, on_tick=...)` calls callback for ticks `[1,2,3]`.
- [ ] Replace obsolete tick-8 Mira/Kaspar teleport expectation with assertion that DayService no longer moves them by itself.
- [ ] Implement per-tick persistence/callback; preserve phase labels.
- [ ] Run day tests.

### Task 3: Mira need/goal/action loop

**Files:** create `src/samseberpg/living_world.py`, modify `tests/test_living_world.py`

- [ ] Write RED test: tick 2 and 4 consume two wood/work cycles; next evaluation creates exactly one `NPC_REQUESTED_RESOURCE` when stock is empty.
- [ ] Implement `LivingWorldService.tick(conn, world_time)` and event writer.
- [ ] Mira works only on even ticks with stock, requests once at zero stock, then waits without event spam.
- [ ] Run focused tests.

### Task 4: Kaspar supply chain

**Files:** `src/samseberpg/living_world.py`, `tests/test_living_world.py`

- [ ] Write RED full-chain test proving request → move → collect `driftwood_1` → return → delivery.
- [ ] Implement one autonomous action per tick using the existing 3-node location graph.
- [ ] Collection sets item `location_id=NULL` and carrying=1.
- [ ] Delivery increments Mira stock, clears request, resets carrying and appends `NPC_DELIVERED_RESOURCE`.
- [ ] Run focused tests.

### Task 5: Wire Living World into authoritative time

**Files:** `src/samseberpg/game.py`, `tests/test_living_world.py`

- [ ] Write RED equivalence test: one `WAIT 9` vs nine `WAIT 1` produce equal Mira/Kaspar/resource state and autonomous event types.
- [ ] Add `self.living_world` and private `_advance_world()` using `DayService.advance(..., on_tick=self.living_world.tick)`.
- [ ] Route all successful MOVE/TAKE/DROP/THROW/TALK/GIVE/FEED/WAIT time advancement through `_advance_world`; LOOK stays free.
- [ ] Run Living World + full regression suite.

### Task 6: Shared player/NPC resource state

**Files:** `src/samseberpg/social.py`, `tests/test_social.py`, `tests/test_living_world.py`

- [ ] Write RED intervention test: player takes `driftwood_1` before Kaspar; no `NPC_COLLECTED_RESOURCE`/delivery can occur.
- [ ] Write RED integration test: player gives useful wood to Mira after request; same `wood_stock` increases and request clears.
- [ ] Extend Mira gift handling to mutate the shared wood need atomically while keeping existing social anti-farm reward logic separate.
- [ ] Run focused + full tests.

### Task 7: Visibility, report, demo, docs

**Files:** `src/samseberpg/social.py`, `src/samseberpg/reporting.py`, `scripts/playtest_report.py`, create `scripts/demo_living_world.py`, `README.md`, `docs/playtests/founder-v0.1.md`, relevant tests.

- [ ] Write RED tests for state-aware TALK and report fields `world_events_total`, `world_event_counts`, `latest_world_events`.
- [ ] Implement compact causal summaries without internal goal IDs or quest text.
- [ ] Implement deterministic demo that triggers autonomous chain with LOOK/WAIT only, verifies persistence, prints event timeline, ends `LIVING WORLD DEMO PASS`.
- [ ] Update README/playtest protocol with the product question: did an NPC-caused change make the player want to intervene?
- [ ] Run final verification:

```bash
python -m compileall -q src scripts
python -m pytest -q
PYTHONPATH=src python scripts/demo_pilot.py
PYTHONPATH=src python scripts/demo_first_day.py
PYTHONPATH=src python scripts/demo_living_world.py
```

## Completion Gate

- [ ] Autonomous Mira → Kaspar → Mira chain occurs without direct player command.
- [ ] Events are deterministic, persistent, separately logged.
- [ ] `WAIT N` equivalence proven.
- [ ] Player can block and satisfy the same physical resource chain.
- [ ] SQLite reopen preserves state/history.
- [ ] Existing first-day/Behavior Engine suite remains green.
- [ ] No LLM or general planner introduced.
- [ ] Demo proves Living World v0 from a clean DB.
