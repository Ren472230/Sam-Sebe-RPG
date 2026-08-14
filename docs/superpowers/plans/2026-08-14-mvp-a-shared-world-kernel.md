# MVP-A Shared World Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested multiplayer-first persistent village kernel where 2–5 players share one authoritative SQLite world, actions are atomic/idempotent, and NPC state catches up to real time lazily.

**Architecture:** A small Python package exposes `GameDatabase`, `WorldSynchronizer`, and `GameService`. The simulation owns canonical mutations; adapters only submit `CanonicalAction` values and read `WorldView`. SQLite write actions use `BEGIN IMMEDIATE`, and a replaceable `Clock` makes offline catch-up deterministic in tests.

**Tech Stack:** Python 3.12+, standard library (`sqlite3`, `dataclasses`, `enum`, `datetime`, `json`), pytest.

## Global Constraints

- Python 3.12+; direct sqlite3, no ORM.
- pytest is the only initial development dependency.
- One process and one SQLite DB.
- Only deterministic simulation/application code may mutate canonical state.
- State mutation and ActionEvent persistence are atomic.
- `external_id` is an idempotency key.
- Players cannot advance shared world time.
- No Discord or LLM dependency in this kernel.
- No combat, crafting, crime, organizations, web UI, dynamic lighting, Redis, PostgreSQL, microservices, RAG, or per-second simulation.

## Planned file map

- `pyproject.toml` — package metadata and pytest config.
- `README.md` — setup and demo instructions.
- `src/samseberpg/domain.py` — actions/results/views/enums.
- `src/samseberpg/clock.py` — Clock protocol, SystemClock, FakeClock.
- `src/samseberpg/db.py` — schema, connection policy, bootstrap and persistence queries.
- `src/samseberpg/world.py` — schedule resolution and lazy catch-up.
- `src/samseberpg/game.py` — authoritative registration, observation and action execution.
- `tests/test_database.py` — schema/bootstrap/registration/persistence.
- `tests/test_shared_world.py` — observation and shared TAKE/DROP behavior.
- `tests/test_time_and_idempotency.py` — catch-up and replay safety.
- `tests/test_concurrency.py` — simultaneous TAKE conflict.
- `scripts/demo_shared_world.py` — deterministic two-player proof.

### Task 1: Package, domain, Clock and SQLite bootstrap

- [ ] Write failing tests that initialize a temporary DB twice, assert one world, three locations, three NPCs, at least ten entities, `stone_flat_1` at `workshop_yard`, and `PRAGMA foreign_keys = 1`.
- [ ] Run the focused test and confirm failure before implementation.
- [ ] Implement `ActionType`, `CanonicalAction`, `ActionResult`, `WorldView`, `VisibleActor`, `VisibleEntity`, `Clock`, `SystemClock`, `FakeClock`, and `GameDatabase`.
- [ ] Implement schema for worlds, locations, location_edges, actors, players, npcs, npc_schedule, entities, relations, action_events and processed_interactions.
- [ ] Bootstrap the village idempotently.
- [ ] Run focused and full tests; commit `feat: bootstrap shared world database`.

### Task 2: Idempotent player registration and shared observation

- [ ] Write failing tests proving two Discord IDs create two player actors in the same world, duplicate registration returns the same actor, and both initially observe the same stone.
- [ ] Implement `GameService(db, clock)`, `register_player(discord_user_id, name) -> str`, and `observe(player_id) -> WorldView`.
- [ ] WorldView must include location metadata, visible actors excluding self, visible entities and owned inventory.
- [ ] Run focused and full tests; commit `feat: add shared player observation`.

### Task 3: Atomic MOVE/TAKE/DROP and events

- [ ] Write failing tests for adjacent MOVE, invalid MOVE, TAKE ownership transfer, cross-player disappearance, DROP return, and failure events.
- [ ] Implement `GameService.execute(action, external_id=None) -> ActionResult` using `BEGIN IMMEDIATE`.
- [ ] Validate and mutate in the same transaction; append exactly one action event for every non-duplicate attempt.
- [ ] Result codes: `OK`, `PLAYER_NOT_FOUND`, `INVALID_DESTINATION`, `TARGET_NOT_FOUND`, `TARGET_NOT_PRESENT`, `NOT_PORTABLE`, `ALREADY_OWNED`, `ITEM_NOT_OWNED`.
- [ ] Run focused/full tests; commit `feat: add atomic shared world actions`.

### Task 4: Idempotency and restart persistence

- [ ] Write a failing test executing TAKE twice with `external_id="discord-123"`; second response must have `replayed=True`, ownership changes once and only one event exists.
- [ ] Write a restart test reopening the DB and verifying ownership/event history.
- [ ] Store/replay the original result inside the same transaction as the first action.
- [ ] Run focused/full tests; commit `feat: make actions idempotent across retries`.

### Task 5: Lazy real-time NPC catch-up

- [ ] Write a FakeClock test: at 08:00 UTC Mira is in `workshop_yard`; advance to 20:00 UTC; next observation places Mira in `village_square` with updated activity and advances `last_simulated_at`.
- [ ] Implement `WorldSynchronizer.catch_up(conn, world_id, now)` with normal and midnight-wrapping schedule windows.
- [ ] Do not replay missed ticks; compute the currently applicable schedule.
- [ ] `observe` and `execute` call catch-up before reading/validating state.
- [ ] Ensure only SystemClock calls `datetime.now()`.
- [ ] Run tests; commit `feat: add lazy realtime npc catchup`.

### Task 6: Concurrent conflict safety

- [ ] Create a thread/barrier test launching two TAKEs for one stone using distinct players/external IDs.
- [ ] Assert exactly one success, one gameplay failure, one final owner and two events.
- [ ] Configure SQLite busy timeout/transaction handling if needed; do not add distributed locks.
- [ ] Run the concurrency test repeatedly and then full suite; commit `test: verify concurrent world mutations serialize`.

### Task 7: Executable proof and runbook

- [ ] Implement `scripts/demo_shared_world.py`: register two players, show shared stone, Player A takes it, Player B no longer sees it, reopen DB, advance FakeClock and show Mira moved.
- [ ] Add README install/test/demo commands.
- [ ] Run `python -m compileall src scripts`, `pytest -q`, and the demo from a clean DB.
- [ ] Commit `docs: add shared world kernel demo and runbook`.

## Completion gate

Kernel is complete only when all tests pass, two players share one authoritative world, cross-player consequences persist after restart, duplicate external IDs are safe, FakeClock drives NPC catch-up, concurrent TAKE yields exactly one success, the simulation has no Discord/LLM dependency, and the demo proves the path end-to-end.
