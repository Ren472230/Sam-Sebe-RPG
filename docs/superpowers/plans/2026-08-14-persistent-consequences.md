# Persistent Consequences Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add deterministic THROW/GIVE actions that mutate visible object state and NPC relationships while producing structured event evidence.

**Architecture:** Extend the existing domain and GameService without adding a new service tier. Canonical action validation, entity mutation, witness lookup, relation mutation and event append remain inside one SQLite write transaction. Presentation consumes richer WorldView state only.

**Tech Stack:** Existing Python 3.12+/sqlite3/pytest kernel; no new dependency.

## Global Constraints

- Preserve the authoritative GameService boundary.
- No RNG in THROW v0.
- Do not add combat, crime, economy or LLM logic.
- Witness consequences depend on canonical NPC location at action time.
- Event evidence must describe committed changes exactly.
- All prior tests remain green.

### Task 1: Extend canonical action/entity models

**Files:**
- Modify `src/samseberpg/domain.py`.
- Modify `src/samseberpg/db.py` bootstrap item state.
- Modify `src/samseberpg/game.py` observation decoding.
- Test `tests/test_consequences.py`.

- [ ] Write a failing test showing `VisibleEntity.state` exposes `tavern_sign.condition == 100` and throwable stones expose their canonical state.
- [ ] Verify RED.
- [ ] Add `THROW`, `GIVE`, `CanonicalAction.item_id`, `VisibleEntity.state`.
- [ ] Give stones `throwable=true` and `impact_damage=20` in bootstrap.
- [ ] Decode entity `state_json` into WorldView.
- [ ] Run focused/full tests and verify GREEN.

### Task 2: Deterministic THROW with structured evidence

**Files:**
- Modify `src/samseberpg/game.py`.
- Test `tests/test_consequences.py`.

- [ ] Write failing tests for item ownership, throwable validation, target presence/damageability and successful tavern-sign damage.
- [ ] Verify RED.
- [ ] Implement THROW in the existing action transaction.
- [ ] Successful THROW moves the projectile to the current location and mutates target condition by deterministic impact damage.
- [ ] Change event append to accept exact evidence dict and persist it as JSON.
- [ ] Verify event evidence contains item/target/damage/before/after.
- [ ] Run focused/full tests and verify GREEN.

### Task 3: Witness-aware Oren relationship consequence

**Files:**
- Modify `src/samseberpg/game.py`.
- Test `tests/test_consequences.py`.

- [ ] Write failing tests proving Oren present -> trust -3/conflict +4, Oren absent -> no relation row/delta.
- [ ] Verify RED.
- [ ] Add relation-upsert helper with bounded values and timestamp.
- [ ] Resolve witnesses from actors at the action location after world catch-up and before mutation completion.
- [ ] Record witnesses and exact relation deltas in THROW evidence.
- [ ] Verify restart persistence.

### Task 4: GIVE and positive relation mutation

**Files:**
- Modify `src/samseberpg/game.py`.
- Test `tests/test_consequences.py`.

- [ ] Write failing tests for GIVE food to present NPC, absent target failure and player-to-player transfer.
- [ ] Verify RED.
- [ ] Implement ownership transfer to target actor.
- [ ] For edible item to NPC, apply trust +2/affinity +1 and record exact evidence.
- [ ] Run focused/full tests and verify GREEN.

### Task 5: Parser and presentation

**Files:**
- Modify `src/samseberpg/parser.py`.
- Modify `src/samseberpg/presentation.py`.
- Modify `tests/test_parser.py`.
- Modify `tests/test_discord_app.py`.

- [ ] Write failing parser tests for Russian/English THROW/GIVE forms.
- [ ] Write failing rendering test for visible condition.
- [ ] Verify RED.
- [ ] Implement explicit grammar and readable condition rendering.
- [ ] Add Discord application integration tests proving actions still route through GameService/idempotency.
- [ ] Run focused/full tests and verify GREEN.

### Task 6: End-to-end consequence demo and verification

**Files:**
- Create `scripts/demo_consequences.py`.
- Modify `README.md`.

- [ ] Demo: two players register; Ren takes stone; moves to square; throws at sign; second player observes 80% sign; Oren relation is negative; restart preserves it; food GIVE produces positive relation evidence in a fresh target/scenario.
- [ ] Run compileall, full pytest, kernel demo and consequence demo.
- [ ] Verify no new dependencies and no direct DB mutation outside db/world/game core.
