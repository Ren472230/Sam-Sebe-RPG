# Emergent Progression v0 Implementation Plan

**Goal:** Implement one evidence-derived `Behavior -> Achievement -> Skill` branch whose persistent ability changes future THROW mechanics.

**Architecture:** Add schema v3 progression ownership tables and a small deterministic `ProgressionEngine`. `GameService` appends the triggering action event, evaluates progression in the same SQLite transaction, stores unlocks in the idempotent ActionResult, and checks canonical abilities during later THROW resolution.

**Tech Stack:** existing Python 3.12 stdlib/sqlite3/pytest project; no new dependency.

## Constraints

- One achievement + one passive ability only.
- No XP/levels/class tree/LLM generation.
- Failed action events do not count.
- Unlock and trigger event commit atomically.
- Duplicate external IDs cannot progress twice.
- Ability affects only future throws, not the triggering throw.

## Tasks

- [x] Schema migration v3 and progression catalog.
- [x] Evidence-derived progression engine with 3 successful throws / 2 projectile IDs threshold.
- [x] Transactional GameService integration and idempotent unlock response.
- [x] Persistent `STEADY_HAND` effect: +5 future THROW damage.
- [x] `/me` and trigger-response presentation.
- [x] End-to-end progression demo and full regression verification.
