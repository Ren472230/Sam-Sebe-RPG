# World Digest v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and TDD task-by-task.

**Goal:** Add a deterministic `/news` return-to-world digest from canonical event/state data.

**Architecture:** A read-only `WorldDigestService` builds a bounded digest after triggering normal lazy catch-up through `GameService.observe`. Discord application/runtime only render and expose this service; no new authoritative mutation path is introduced.

**Tech Stack:** Python 3.12+, sqlite3, dataclasses, existing Discord adapter.

## Global Constraints

- No LLM-generated news in v0.
- No external weather API in v0.
- No new DB schema unless implementation proves it is necessary.
- Read-only digest calls must not append `action_events`.
- Use the requesting player's latest action event ID as the deterministic anchor.
- Show at most 8 notable other-player events.

---

### Task 1: Digest read model and event anchor

**Files:**
- Create: `src/samseberpg/digest.py`
- Create: `tests/test_world_digest.py`

- [ ] Write failing tests for latest-own-event anchor, exclusion of own events, notable action filtering and chronological ordering.
- [ ] Run focused tests and confirm RED.
- [ ] Implement immutable digest dataclasses and `WorldDigestService.build(player_id)`.
- [ ] Run focused tests and confirm GREEN.

### Task 2: Persistent condition and NPC catch-up snapshot

**Files:**
- Modify: `src/samseberpg/digest.py`
- Modify: `tests/test_world_digest.py`

- [ ] Write failing tests proving damaged `tavern_sign` is reported even when older than anchor.
- [ ] Write failing test proving advancing `FakeClock` changes NPC location/activity in the digest.
- [ ] Implement condition snapshot and NPC status query after `GameService.observe` catch-up.
- [ ] Run focused tests and confirm GREEN.

### Task 3: Discord `/news` surface

**Files:**
- Modify: `src/samseberpg/discord_app.py`
- Modify: `src/samseberpg/discord_bot.py`
- Modify: `src/samseberpg/presentation.py`
- Modify: `tests/test_world_digest.py`

- [ ] Write failing application-level rendering test and prove repeated read returns identical content without new events.
- [ ] Add `render_world_digest` and `DiscordGameApplication.handle_news`.
- [ ] Add `/news` slash command in runtime.
- [ ] Run focused tests and compileall.

### Task 4: Demo, docs, regression verification

**Files:**
- Create: `scripts/demo_world_digest.py`
- Modify: `README.md`

- [ ] Demonstrate A action -> B damages sign -> clock advances -> A news sees event + damage + new NPC state.
- [ ] Run focused suite, existing repaired progression/TALK tests, compileall and demo.
- [ ] Sync only the verified state to the feature branch.
