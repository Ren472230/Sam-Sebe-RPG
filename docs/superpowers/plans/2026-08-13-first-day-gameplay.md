# First Day Gameplay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the technical Pilot v0.1 into one coherent first playable day with a soft lodging motivation, time/NPC movement, deterministic social interactions and systemic consequences.

**Architecture:** Extend the authoritative `GameService`; keep schedules and social rules in focused services. Persist only the minimum player resources and reuse relations/events. Parsers only create proposals.

**Tech Stack:** Python 3.12+, sqlite3, standard library, pytest; optional local Ollama over HTTP.

## Global Constraints

- `GameService` remains the only authoritative state mutation path.
- No quest/task log.
- No health/hunger/thirst, combat, crafting, full economy, LLM NPC dialogue, Discord, multiplayer concurrency, or extra locations/NPCs.
- `LOOK` consumes no game time; successful meaningful actions consume time.
- NPC schedules are deterministic/lazy.
- LLM never mutates SQLite directly.
- repeated identical contribution tags cannot farm money/trust.
- existing throwing progression must remain green.

---

### Task 1: Persistent day state and schedules

- [x] Add `player_resources` (`coins`, `lodging_secured`) with migration-safe bootstrap.
- [x] Add `DayService.advance`, phase mapping and lazy schedule application.
- [x] Move Mira/Kaspar to the square at tick 8+.
- [x] Keep LOOK free; advance meaningful successful actions.
- [x] Cover bootstrap, migration, time and schedules with tests.

### Task 2: TALK / GIVE / FEED

- [x] Add `ActionType.TALK`.
- [x] Add deterministic `SocialService`.
- [x] Implement present-NPC TALK.
- [x] Implement tag-based GIVE with one-time contribution rewards.
- [x] Implement FEED for present animals and food items.
- [x] Persist NPC trust and raven trust.
- [x] Add behavior/evidence tags and tests.

### Task 3: Lodging with protected player agency

Initial plan was refined during implementation: asking about lodging must not auto-spend or auto-complete anything.

- [x] `topic=lodging` only explains conditions.
- [x] `topic=pay_lodging` explicitly pays 3 coins.
- [x] `topic=request_lodging` explicitly uses Mira/Kaspar trust >=3.
- [x] Persist lodging state.
- [x] Add an organic reachable social route via three distinct Mira-useful contributions, including `driftwood_1`.
- [x] Verify no quest/task table or visible skill requirement is introduced.

### Task 4: Consequences and anti-grind

- [x] Successful hit on `target_sign` lowers Oren trust.
- [x] Miss has no social penalty.
- [x] Duplicate contribution tags cannot create unlimited rewards.
- [x] Keep social effects in ActionEvent evidence.
- [x] Re-run original throwing/progression regression tests.

### Task 5: Parser, CLI, reporting and demos

- [x] Deterministic parser supports TALK/GIVE/FEED and explicit lodging actions.
- [x] Ollama schema supports new action types and canonical lodging topics.
- [x] Reject LLM-invented entity IDs and noncanonical topics.
- [x] CLI shows first-day intro, day phase, coins and lodging without quest log.
- [x] Extend playtest report with first-day resources and trust.
- [x] Add `scripts/demo_first_day.py` as one example route, not the only solution.
- [x] Preserve and run `scripts/demo_pilot.py`.
- [x] Update README and founder playtest protocol.

## Completion verification

- [x] Existing technical vertical slice remains green.
- [x] Practical situation is visible without a quest list.
- [x] Time changes NPC positions independently.
- [x] TALK/GIVE/FEED produce persistent consequences.
- [x] Two explicit lodging routes exist: coins and trust.
- [x] Ignoring lodging remains legal; no hard stop/game-over.
- [x] Throwing still emerges into `aimed_throw` without instruction.
- [x] Both demos run from clean SQLite databases.
- [x] Full regression suite passes locally.

Final product evidence still requires the real 30–60 minute founder playtest; automated tests prove system behavior, not fun.
