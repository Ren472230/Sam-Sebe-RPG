# Emergent Progression v0 — Design Specification

## Goal

Prove the core fantasy `Behavior -> Achievement -> Skill` with one deterministic progression branch derived from actual persistent action evidence. The player does not pick a class or press an unlock button; the system notices repeated behavior and changes future mechanics.

## Smallest proof

1. Player successfully throws objects three times.
2. Those throws use at least two distinct projectile entity IDs.
3. On the third qualifying throw, achievement `THROWING_HABIT_1` / "Рука помнит дугу" unlocks exactly once.
4. The same transaction also unlocks passive ability `STEADY_HAND` / "Твёрдая рука".
5. `/me` shows both unlocks.
6. Future successful THROW actions by that player receive +5 deterministic impact damage.
7. Restart preserves unlocks and the bonus.

This tests behavior detection, persistent unlock state and a real mechanical consequence without adding a class system or an AI-generated achievement engine.

## Scope

Included: one achievement branch; deterministic event-derived evaluation; schema migration v3; canonical player achievement/ability tables; progression evaluation inside the same gameplay write transaction; unlock notice; persistent `/me` visibility; one passive THROW effect.

Deferred: XP, levels, classes, skill trees, LLM-generated achievements/mechanics, active ability syntax, respec, team progression and a generic rules DSL.

## Persistence

Schema version becomes `3`.

`player_achievements` stores player, achievement code, unlock time, trigger event and structured evidence. `player_abilities` stores player, ability code, unlock time and source achievement. Display metadata stays in a tiny deterministic code catalog.

## Deterministic rule

Achievement `THROWING_HABIT_1` / `Рука помнит дугу` requires at least 3 successful THROW events and at least 2 distinct `evidence_json.item_id` values. Failed throws never count.

It grants `STEADY_HAND` / `Твёрдая рука`. Future THROW actions add +5 impact damage. The triggering third throw is resolved before the unlock, so the bonus starts with the next throw.

## Transaction flow

`GameService` resolves action → appends event → evaluates progression → merges newly-created unlock metadata into the final `ActionResult` → stores idempotent interaction result → commits. A duplicate interaction is replayed before resolution, so it cannot progress twice.

`action_events.evidence_json` remains evidence of the action itself. Progression provenance lives in `player_achievements.evidence_json` and `trigger_event_id`.

## Presentation

`WorldView` exposes achievement and ability codes. `/me` renders their display names. The trigger response includes compact `🏆` achievement and `✨` skill lines.

## Definition of Done

The current village can organically produce "Рука помнит дугу" from repeated throwing behavior; the unlock is persistent and idempotent; it grants `STEADY_HAND`; `/me` and the trigger response show it; a later THROW demonstrably changes from 20 to 25 damage because of the earned ability; schema migration is safe; all previous multiplayer, economy, migration, Discord and semantic-intent regressions remain green.
