# SQLite Schema Migrations — Design Specification

## Goal

Make founder playtests safe across application updates. A previously created `game.db` must start under the current build without deleting persistent player/world state, while a database from a newer unknown build must fail fast instead of being guessed at.

## Problem

`CREATE TABLE IF NOT EXISTS` creates missing tables but does not evolve existing columns or seed affordance JSON. The economy slice added `npcs.coins`, bottle sale metadata and a well water-source affordance. A DB created by an earlier build can therefore be structurally valid enough to open but fail at runtime or silently miss newer deterministic rules.

## Version mechanism

Use SQLite `PRAGMA user_version` as the single integer schema/data-contract version. No migration framework dependency.

Current target: `SCHEMA_VERSION = 2`.

`GameDatabase.initialize()`:
1. opens one write transaction;
2. rejects `user_version > SCHEMA_VERSION`;
3. runs idempotent `CREATE TABLE IF NOT EXISTS` statements;
4. applies ordered migrations from the current version to the target;
5. advances `PRAGMA user_version` only after each migration succeeds;
6. commits atomically, otherwise rolls back.

## Migration 1 — NPC currency

Purpose: make legacy pre-economy DBs compatible with BUY.

- Inspect `PRAGMA table_info(npcs)`.
- If `coins` is absent, run `ALTER TABLE npcs ADD COLUMN coins INTEGER NOT NULL DEFAULT 0 CHECK(coins >= 0)`.
- Only when the column was newly added, seed existing `npc_oren` to 20 coins. This avoids overwriting a balance in any DB that already had the column.

Fresh databases may already contain the latest column because `SCHEMA` is current; migration 1 then performs no structural change.

## Migration 2 — deterministic affordance seed evolution

Upgrade known seed entities without resetting canonical ownership, location, damage, or later player-created state.

Merge missing keys only:
- `stone_flat_1`, `stone_round_1`: `throwable=true`, `impact_damage=20`;
- `bottle_1`: `price=3`, `for_sale_by=npc_oren`, `fillable=true`, `filled_with=null`;
- `village_well`: `water_source=true`.

Use Python JSON decoding/encoding rather than relying on SQLite JSON1 availability. Existing keys always win (`setdefault` semantics). Missing entities are tolerated because bootstrap may not have run yet.

## Compatibility rules

- Do not recreate or truncate tables.
- Do not reset player coins, ownership, relations, events, object condition or filled state.
- Do not silently downgrade a DB with `user_version` newer than supported.
- Migration code lives in `db.py`; gameplay services do not know schema versions.
- Bootstrap remains idempotent and always creates latest seed state for an empty DB.

## Tests

Required:
- fresh DB initializes to current `SCHEMA_VERSION`;
- a legacy DB whose `npcs` table lacks `coins` upgrades and existing world/player/event rows survive;
- Oren gets 20 only when the coins column is newly introduced;
- legacy entity JSON gets missing affordances;
- existing canonical values (e.g. sign condition, filled bottle, already-present keys) are not reset;
- calling `initialize()` repeatedly is idempotent;
- a future `user_version` fails fast with a typed application exception;
- all gameplay/Discord/concurrency tests remain green.

## Definition of Done

An old pre-economy SQLite file upgrades in place and can execute current GameService observation/BUY rules without manual deletion; a current DB is unchanged by repeated initialization; unknown future versions are rejected; the full existing suite and demos remain green.
