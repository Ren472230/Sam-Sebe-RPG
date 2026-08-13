# Audit Fix Pack A — Decision-Quality Founder Playtest Design

Date: 2026-08-13
Status: approved direction from capital audit; implementation may proceed autonomously

## Goal

Make Pilot v0.1 capable of producing decision-quality founder-playtest evidence without expanding the game into Living World v1, combat, economy, more NPCs, or a generalized mechanic compiler.

The repaired loop is:

```text
raw player input
→ parser attempt evidence
→ CanonicalAction
→ authoritative player mutation
→ deterministic time advance
→ Living World reaction
→ player-observable world feedback
→ completion-timed ActionEvent
→ progression / report evidence
```

The core design principle is that simulation, presentation, and telemetry must describe the same causal sequence.

## Approaches considered

### A. Minimal patch-per-finding

Independently hide help entries, add one telemetry table, tweak reward numbers, and add a few consequences.

Pros: smallest diff.
Cons: preserves inconsistent action timing and makes observability an afterthought; likely creates more special cases in `game_base.py`.

### B. Completion-oriented action finalization — chosen

Keep current deterministic resolvers but introduce one common timed-action finalization contract. Timed actions mutate their immediate authoritative state, advance time, collect same-location autonomous events, then write the player action as a completion event. Telemetry and UX attach around this boundary.

Pros: directly fixes causal ordering, enables Living World presentation, keeps old resolver semantics, and provides a clean future seam.
Cons: touches every successful time-consuming action and therefore needs strong regression tests.

### C. Full event-sourced rewrite

Replace action handlers with commands/events/reducers and build a unified replay timeline.

Pros: clean long-term model.
Cons: severe scope expansion before product evidence. Rejected.

## Scope

Implement all P0 findings from the capital audit plus the P1 protections that are required by these structural changes:

1. founder-safe vs systems/debug help;
2. persistent `input_attempts` telemetry;
3. explicit action start/resolution time semantics;
4. same-location observable Living World feedback;
5. lodging-route rebalance without new content;
6. minimal consequences for hitting NPCs/animals;
7. one positive systemic use of `aimed_throw`;
8. schema version + explicit migration because the DB schema changes;
9. invariant tests for the touched simulation contracts;
10. CI and design-spec synchronization.

Explicitly defer:

- generic NPC knowledge/messages;
- resource ecology/respawn;
- generalized item containment;
- Living World v1;
- generic mechanic generation;
- multiplayer concurrency;
- combat/health;
- new locations/NPCs/items.

## 1. CLI modes and spoiler control

Add `--mode founder|systems`, default `founder`.

### Founder mode

`help` shows only meta-level guidance:

- write what you want to do in ordinary language when Ollama is enabled;
- `осмотреться` as a grounding command;
- `help`;
- `quit`.

It must not enumerate GIVE/FEED/THROW/TALK families or reward routes.

If no Ollama model is configured, founder help may say that the current build understands a limited command language, but it still must not list the action catalogue.

Locked ability syntax is never shown before unlock. After `aimed_throw` unlocks, founder mode may reveal only that newly learned affordance.

### Systems mode

Shows the complete canonical command reference. `прицельно бросить` appears only when `aimed_throw` is unlocked.

Founder playtest documentation must use `--mode founder`; systems-only diagnostics use `--mode systems`.

## 2. Input-attempt telemetry

Add append-only local SQLite table:

```text
input_attempts
- attempt_id INTEGER PRIMARY KEY AUTOINCREMENT
- world_time INTEGER NOT NULL
- raw_text TEXT NOT NULL
- parser_mode TEXT NOT NULL          # deterministic | ollama | none
- parser_model TEXT
- recognized INTEGER NOT NULL
- canonical_action_json TEXT
- result_code TEXT
- parser_error TEXT
- latency_ms REAL
```

One row represents one player-entered gameplay input, not each internal fallback stage.

Resolution rules:

- deterministic parser succeeds → `parser_mode=deterministic`;
- deterministic parser misses and Ollama succeeds/fails → `parser_mode=ollama`;
- deterministic parser misses with no Ollama configured → `parser_mode=none`;
- parser exception still creates a row with `recognized=false` and `parser_error`;
- after GameService execution, update `result_code` for that attempt.

Telemetry never affects authoritative game outcomes.

`build_playtest_report` adds aggregate input metrics only; human report does not print raw player text by default.

## 3. Action time contract

Keep `action_events.world_time` for backward compatibility but define it as **resolved/completion tick**.

Add:

```text
started_at_tick INTEGER NOT NULL
resolved_at_tick INTEGER NOT NULL
duration_ticks INTEGER NOT NULL
```

Contract:

- LOOK and failed actions: start = resolve, duration = 0;
- normal successful time-consuming actions: resolve = start + 1, duration = 1;
- WAIT N: resolve = start + N, duration = N;
- `world_time == resolved_at_tick` for every new action event.

Timed success flow:

1. capture start tick and current last `world_event` id;
2. apply the player's immediate authoritative mutation;
3. advance deterministic time;
4. Living World reacts during each tick;
5. collect world events created during that advance;
6. write the player action with completion-time semantics;
7. run progression that depends on the newly written player event;
8. return the action result plus observable world feedback.

Failures do not advance time and are logged at the current tick.

## 4. Player-observable Living World events

Do not expose the global `world_events` stream during ordinary play.

After a timed action, collect only new autonomous events whose `location_id` equals the player's authoritative location after the player's immediate mutation.

Attach compact structured entries to:

```text
ActionResult.data["observed_world_events"]
```

CLI renders them after the direct player-result sentence.

Initial v0 observability is intentionally strict:

- same-location → visible;
- off-screen → hidden;
- no omniscient summaries;
- no adjacent-location audio heuristics yet.

This makes the founder test ask whether the player notices actual local consequences, not debug logs.

## 5. First-day route rebalance

Use only existing items/NPCs.

### Gift rewards

Mira:

- `flat_stone`: +1 trust, +1 coin first unique contribution;
- `round_stone`: +1 trust, +1 coin first unique contribution;
- `useful_wood`: +1 trust, 0 coins.

Kaspar:

- `pinecone`: +1 trust, +1 coin first unique contribution.

### Lodging social route

A local can vouch at trust >= 2 instead of 3.

Consequences:

- two starter stones no longer immediately fund the 3-coin room;
- the money route naturally encourages at least one additional interaction/exploration;
- Mira's social route remains reachable without winning the hidden driftwood race;
- no new quest flags or items are introduced.

These are Pilot numbers, not permanent balance.

## 6. Consequence consistency for thrown objects

Do not introduce HP/combat.

On a successful THROW hit:

### NPC target

- target NPC trust toward player: -2;
- NPC `state_json.hit_by_player_count += 1`;
- direct action summary mentions the hostile reaction;
- TALK with a negatively trusting NPC uses a short cold/refusal-style summary.

### Raven target

- `fear += 2`;
- `trust -= 1` with no lower clamp required in v0;
- raven moves deterministically away to the other non-workshop public location (`village_square ↔ river_edge`) when possible;
- summary reports that it flees.

These are social/animal consequences, not combat simulation.

## 7. One positive use of `aimed_throw`

Use the existing `target_barrel` and Mira; add no new entity.

When all are true:

- action is `THROW` with `aimed=true`;
- target is `target_barrel`;
- hit succeeds;
- barrel has not already been precision-fixed;
- Mira is present at `workshop_yard`;

then:

- set `target_barrel.state_json.precision_fixed = true`;
- Mira trust toward player +1 once;
- result/evidence records `precision_task_completed=true`;
- summary explains that the accurate impact knocked a warped hoop/part back into place and Mira noticed.

This gives the first emergent ability one interpretable positive application without adding a task system or new reward branch.

## 8. Schema version and migration

Add `world_meta.schema_version` and set latest version to `2`.

Version 1 represents the pre-audit Pilot schema.

Migration `1 → 2`:

- create `input_attempts`;
- add `started_at_tick`, `resolved_at_tick`, `duration_ticks` to `action_events` if missing;
- backfill old action rows conservatively with `started_at_tick = world_time`, `resolved_at_tick = world_time`, `duration_ticks = 0` because historical duration cannot be reconstructed reliably;
- set schema version to 2.

Fresh databases are created directly at the latest shape. Migration code must be idempotent.

## 9. Tests and invariants

Keep existing regression scenarios and add tests for:

- founder help hides action catalogue and locked ability;
- systems help exposes canonical commands but hides locked ability until unlock;
- every player input produces telemetry, including parse miss and Ollama error;
- telemetry completion stores GameService result code;
- new action rows obey `world_time == resolved_at_tick` and duration rules;
- failed actions do not advance world time;
- same-location world events are returned/rendered while off-screen events are hidden;
- two starter stones produce 2 coins and Mira trust 2;
- social lodging succeeds at trust 2;
- money lodging requires an additional contribution beyond the two starter stones;
- NPC hit changes trust/state;
- raven hit changes fear/trust/location;
- precision barrel consequence is one-shot and requires unlocked aimed throw;
- old-schema DB migrates to version 2 without losing entity/player state;
- one item cannot become duplicated by the touched player/Kaspar flows;
- an NPC still performs at most one Living World action per tick;
- WAIT equivalence remains green.

## 10. CI and documentation

Add a small GitHub Actions workflow for Python 3.12 that runs:

```text
python -m compileall -q src scripts
pytest -q
```

No coverage gate yet.

Update first-day design with an explicit amendment: the old tick-8 Mira/Kaspar teleport is superseded by Living World autonomous movement.

Update README and founder playtest commands/interpretation for CLI modes and input telemetry.

## Completion gate

Fix Pack A is technically complete only when:

1. full existing + new test suite passes;
2. all three existing demos still pass;
3. a new founder-readiness smoke test demonstrates hidden help, input telemetry, observable autonomous feedback, rebalance, and consequence consistency;
4. old DB migration is proven;
5. GitHub branch contains the exact verified production/test snapshot;
6. PR remains unmerged until explicit user instruction.

Passing this gate means **ready to run the founder playtest**, not that the game hypothesis is validated.