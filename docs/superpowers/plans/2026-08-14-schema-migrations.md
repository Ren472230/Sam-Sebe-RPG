# SQLite Schema Migrations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Safely evolve existing founder SQLite files to the current schema/data contract without resetting canonical world state.

**Architecture:** `GameDatabase.initialize()` owns an ordered, dependency-free migration runner driven by SQLite `PRAGMA user_version`. Migrations are transactional, introspective where needed, and idempotent.

**Tech Stack:** Python stdlib + sqlite3 + pytest.

### Task 1: Version contract and future-version guard
- [ ] RED tests for fresh DB target version and unsupported future DB.
- [ ] Add `SCHEMA_VERSION` and `UnsupportedSchemaVersionError`.
- [ ] Make initialize transactional and fail fast when DB version is newer.
- [ ] GREEN full suite.

### Task 2: Legacy NPC currency migration
- [ ] RED fixture DB with full legacy schema but no `npcs.coins`; preserve existing player/event rows.
- [ ] Introspect table columns; add `coins` only if absent; seed Oren 20 only on column introduction.
- [ ] Prove repeated initialize does not reset a changed Oren balance.
- [ ] GREEN full suite.

### Task 3: Seed affordance data migration
- [ ] RED tests for legacy stone/bottle/well JSON and preservation of existing keys/state.
- [ ] Merge missing affordance keys via Python JSON with `setdefault` semantics.
- [ ] Advance `user_version` only after successful migration.
- [ ] GREEN full suite.

### Task 4: Upgrade proof and verification
- [ ] Add `scripts/demo_migration.py` that builds a representative legacy DB, upgrades it, and proves current observation/economy behavior without losing an existing player/event.
- [ ] Document migration behavior in README.
- [ ] Run compileall, full pytest, all demos, repeated concurrency test.
