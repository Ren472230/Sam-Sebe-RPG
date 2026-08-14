# Deterministic NPC Dialogue v0 Implementation Plan

**Goal:** Turn successful canonical TALK into relationship-aware character dialogue without giving prose any authority over game state.

## Tasks

- [ ] TDD persona catalog and neutral TALK rendering from NPC activity.
- [ ] TDD relationship branches for positive trust/affinity and conflict/negative trust.
- [ ] Prove renderer performs no DB writes.
- [ ] Integrate renderer only after successful `ActionType.TALK` in `DiscordGameApplication`.
- [ ] Prove replayed TALK remains one event/one familiarity increment and stable dialogue.
- [ ] Add demo: gift Oren -> warm response; damage sign -> guarded response in a separate scenario.
- [ ] Run repaired progression/TALK + digest + dialogue regression and compileall before sync.
