# First Day Gameplay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing technical Pilot v0.1 into one coherent first playable day with a soft lodging motivation, persistent time/NPC movement, deterministic social interactions, and systemic consequences.

**Architecture:** Extend the existing authoritative `GameService` rather than adding a second gameplay layer. Add small focused services for day-state/schedules and social rules; persist only coins/lodging and reuse the existing relations/events tables. Deterministic parser and optional Ollama parser only create canonical action proposals.

**Tech Stack:** Python 3.12+, sqlite3, dataclasses/enums, pytest, standard library networking for optional Ollama.

## Global Constraints

- `GameService` remains the only authoritative state mutation path.
- No quest/task log.
- No health/hunger/thirst, combat, crafting, full economy, LLM NPC dialogue, Discord, multiplayer concurrency, or extra locations/NPCs.
- `LOOK` consumes no game time; successful meaningful actions consume time.
- NPC schedules are deterministic and applied lazily.
- LLM output can never mutate SQLite directly.
- Repeated identical gifts cannot generate unlimited money/trust.
- Existing throwing progression must continue to pass unchanged.

---

## File map

- `src/samseberpg/domain.py` — add `TALK` canonical action.
- `src/samseberpg/db.py` — add persistent first-day player state and richer bootstrap entity state.
- `src/samseberpg/day.py` — world phase, time advancement, NPC schedule application.
- `src/samseberpg/social.py` — deterministic NPC preferences, trust/coin rewards, lodging rules.
- `src/samseberpg/game.py` — route TALK/GIVE/FEED, apply time and consequences.
- `src/samseberpg/parser.py` — deterministic commands for new actions.
- `src/samseberpg/llm_parser.py` — structured schema support for new actions/topic.
- `src/samseberpg/cli.py` — first-day intro/status rendering.
- `src/samseberpg/reporting.py` — include first-day signals.
- `tests/test_day.py` — time/schedules.
- `tests/test_social.py` — talk/give/feed/lodging/consequences.
- `tests/test_parser.py`, `tests/test_llm_parser.py`, `tests/test_cli.py` — adapter behavior.
- `scripts/demo_first_day.py` — deterministic coherent first-day path.

---

### Task 1: Persistent day state and NPC schedules

**Files:**
- Modify: `src/samseberpg/db.py`
- Create: `src/samseberpg/day.py`
- Create: `tests/test_day.py`

**Interfaces:**
- Produces `DayService.advance(conn, ticks: int) -> int`.
- Produces `DayService.apply_schedules(conn, world_time: int) -> None`.
- Produces `GameDatabase.fetch_player_resources(player_id) -> dict`.

- [ ] Write failing tests proving player resources bootstrap as `{coins: 0, lodging_secured: False}`, LOOK-equivalent reads do not advance time, and at tick 8 Mira/Kaspar move to `village_square` while Oren remains there.
- [ ] Run `pytest tests/test_day.py -v` and confirm RED.
- [ ] Add `player_resources(player_id PRIMARY KEY, coins INTEGER NOT NULL, lodging_secured INTEGER NOT NULL)` and idempotent bootstrap row.
- [ ] Implement `DayService` with schedule rule: ticks `<8` use original Mira/Kaspar locations; ticks `>=8` place both at `village_square`.
- [ ] Run focused test and full suite; confirm GREEN.

### Task 2: Deterministic TALK, GIVE, FEED

**Files:**
- Modify: `src/samseberpg/domain.py`
- Create: `src/samseberpg/social.py`
- Modify: `src/samseberpg/game.py`
- Create: `tests/test_social.py`

**Interfaces:**
- Add `ActionType.TALK`.
- `SocialService.get_trust(conn, source_id, target_id) -> float`.
- `SocialService.apply_gift(conn, player_id, npc_id, item_id, item_tags) -> dict` returns `trust_delta`, `coins_delta`, `accepted_key`.
- `SocialService.feed_animal(conn, player_id, animal_id, item_id) -> dict`.

- [ ] Write failing tests: TALK requires a present NPC; GIVE requires owned item + present NPC; relevant first unique stone gift to Mira gives +1 trust and +2 coins; repeating same reward key gives no second coin/trust reward; FEED requires `food` and raises raven trust.
- [ ] Run focused tests and confirm RED.
- [ ] Add deterministic preference rules: Mira values `flat_stone` and `round_stone`; Kaspar values `pinecone`; store one-time contribution markers in NPC `state_json.received_contributions`.
- [ ] Implement TALK/GIVE/FEED through `GameService`, consuming successful gifts/food and appending evidence-rich events.
- [ ] Advance world time by one tick after successful MOVE/TAKE/DROP/THROW/TALK/GIVE/FEED; LOOK remains free; WAIT advances requested ticks.
- [ ] Run focused and full suite; confirm GREEN.

### Task 3: Lodging and social/economic alternatives

**Files:**
- Modify: `src/samseberpg/social.py`
- Modify: `src/samseberpg/game.py`
- Modify: `tests/test_social.py`

**Interfaces:**
- `TALK` uses `modifiers['topic'] == 'lodging'` for Oren.
- Lodging rule: pay 3 coins OR Mira/Kaspar trust >= 3.

- [ ] Write failing tests for: 2 coins cannot buy lodging; 3 coins spends exactly 3 and persists `lodging_secured`; trust >=3 with Mira secures lodging without spending coins; no route creates a quest/task row or visible skill requirement.
- [ ] Run focused tests and confirm RED.
- [ ] Implement state-aware Oren lodging response and persistent state mutation.
- [ ] Make normal TALK responses reveal situation/context but never enumerate a checklist of exact optimal actions.
- [ ] Run focused and full suite; confirm GREEN.

### Task 4: Consequences and anti-grind rules

**Files:**
- Modify: `src/samseberpg/social.py`
- Modify: `src/samseberpg/game.py`
- Modify: `tests/test_social.py`
- Modify: `tests/test_progression.py`

**Interfaces:**
- Successful hit on `target_sign` applies one deterministic Oren trust penalty per hit.
- Existing `ProgressionService` interface remains unchanged.

- [ ] Write failing test: hitting `target_sign` lowers Oren trust; a miss does not; repeated gift exploit cannot create unlimited coins; throwing progression still unlocks from diverse competent behavior.
- [ ] Run focused tests and confirm RED.
- [ ] Apply sign consequence after resolved THROW without letting social code decide hit/miss.
- [ ] Keep consequences in event evidence (`social_effects`).
- [ ] Run full suite and confirm GREEN.

### Task 5: Parser, CLI, reporting, and first-day demo

**Files:**
- Modify: `src/samseberpg/parser.py`
- Modify: `src/samseberpg/llm_parser.py`
- Modify: `src/samseberpg/cli.py`
- Modify: `src/samseberpg/reporting.py`
- Modify: `README.md`
- Create: `scripts/demo_first_day.py`
- Modify: `tests/test_parser.py`
- Modify: `tests/test_llm_parser.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Deterministic parser supports `поговорить <npc>`, `спросить <npc> о ночлеге`, `дать <item> <npc>`, `покормить <animal> <item>`.
- Ollama schema supports TALK/GIVE/FEED and nullable `topic`.
- CLI header shows day phase, coins, lodging status without rendering a quest list.

- [ ] Write failing parser/CLI tests for new commands and first-day status.
- [ ] Run focused tests and confirm RED.
- [ ] Extend parser and Ollama schema/context validation; unsupported/free-form outputs still fall back safely.
- [ ] Add compact intro/status text and evening state to CLI.
- [ ] Extend playtest report with coins, lodging, NPC trust, animal trust, unscripted-action proxy counts, and world time.
- [ ] Implement `scripts/demo_first_day.py` showing at least one coherent route plus one optional experiment, without hardcoding it as the only solution.
- [ ] Update README and founder playtest protocol.
- [ ] Run `python -m compileall -q src scripts`, full `pytest -q`, original `demo_pilot.py`, and new `demo_first_day.py`.

## Completion gate

- [ ] Existing technical vertical slice remains green.
- [ ] A player has a clear practical situation without a quest list.
- [ ] Time changes the world independently.
- [ ] TALK/GIVE/FEED produce persistent deterministic consequences.
- [ ] At least two routes can secure lodging: coins or trust.
- [ ] Ignoring lodging remains legal.
- [ ] Throwing can still emerge into `aimed_throw` without being instructed.
- [ ] The first-day demo and report run from a clean SQLite database.
