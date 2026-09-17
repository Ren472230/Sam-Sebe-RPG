# Living Conversation v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the four Stream Slice NPCs distinct, stateful, opinionated and capable of grounded initiative, callbacks, refusal and unfinished conversations without weakening authoritative world-state boundaries.

**Architecture:** Preserve the current `DialogueService` authority separation. Add deterministic conversation-state derivation and validated pair-scoped conversational metadata around the existing LLM provider. Keep physical world mutations and canonical facts server-owned; let the LLM generate language plus narrow conversational proposals that the backend validates and persists.

**Tech Stack:** Python 3.12, FastAPI, SQLite, OpenAI Responses API, TypeScript/Vite/Phaser, pytest, Playwright, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-07-living-conversation-v2-design.md`

## Global Constraints

- Base exact SHA: `15db52d9e63bb97c4aeecb15744abac09f2d4b2f`.
- Development branch: `feat/living-conversation-v2`.
- Existing Living World / Living NPC / Social World / Stream Slice behavior must remain compatible.
- LLM never mutates physical world state directly.
- Player claims never become objective facts automatically.
- NPC knowledge remains NPC-scoped and provenance-aware.
- No embeddings, RAG, autonomous LLM planning, dynamic lore, procedural quests or background LLM calls every tick.
- No merge without separate explicit user authorization.

---

### Task 1: Rich NPC voice profiles and anti-chatbot prompt

**Files:**
- Modify: `src/samseberpg/npc_profiles.py`
- Modify: `src/samseberpg/dialogue.py`
- Create: `tests/test_living_conversation_voice.py`

**Interfaces:**
- Extend `NpcProfile` with `values`, `temperament`, `humor_style`, `likes`, `dislikes`, `conversation_preferences`, `avoided_topics`, `warmth_signals`, `conflict_behavior`, `characteristic_phrases`, `forbidden_phrases`, `default_reply_length`.
- `DialogueContext.to_prompt()` serializes these fields.
- `OpenAIResponsesProvider.generate()` contains explicit anti-assistant rules while preserving knowledge/side-effect constraints.

- [ ] Add failing tests asserting all four profiles expose distinct voice-bible data and that prompt text contains anti-chatbot rules.
- [ ] Run CI and confirm the new tests fail before implementation.
- [ ] Implement profile fields for Oren, Mira, Kaspar and Talen.
- [ ] Extend context/prompt/provider instructions minimally.
- [ ] Run CI and confirm voice tests plus all legacy dialogue tests pass.

### Task 2: Deterministic inner state and subjective stance

**Files:**
- Create: `src/samseberpg/conversation_state.py`
- Modify: `src/samseberpg/dialogue.py`
- Create: `tests/test_conversation_state.py`

**Interfaces:**
- Create immutable `NpcInnerState(mood, secondary_mood, current_concern, current_desire, availability, stance)`.
- Create `NpcConversationStateResolver.resolve(npc_id, runtime_state, activity, relation, known_facts) -> NpcInnerState`.
- `DialogueContext` gains `inner_state` and serializes it into provider context.

- [ ] Add failing tests for Mira wood-blocked vs resolved state, Oren hospitality/road concern, Kaspar autonomy stance and Talen road-witness stance.
- [ ] Confirm RED in CI.
- [ ] Implement deterministic resolver with only Stream Slice rules and neutral defaults.
- [ ] Wire resolver into `DialogueService.build_context()`.
- [ ] Confirm GREEN and no regression.

### Task 3: Relationship behavior modes

**Files:**
- Modify: `src/samseberpg/conversation_state.py`
- Modify: `src/samseberpg/dialogue.py`
- Extend: `tests/test_conversation_state.py`

**Interfaces:**
- Create `relationship_behavior(relation: dict[str, int]) -> str` returning one of `guarded`, `neutral`, `comfortable`, `warm`, `distrustful`, `hostile`.
- `DialogueContext` gains `relationship_behavior`.

- [ ] Add failing boundary tests for trust/affinity/conflict/fear combinations.
- [ ] Confirm RED.
- [ ] Implement deterministic mapping without changing stored relation numbers.
- [ ] Include behavior mode in the prompt with instruction to express it indirectly, never as numeric trust.
- [ ] Confirm GREEN.

### Task 4: Pair-scoped conversational memories with provenance

**Files:**
- Modify: `src/samseberpg/db.py`
- Modify: `src/samseberpg/dialogue.py`
- Create: `tests/test_conversation_memory.py`

**Interfaces:**
- Add table `conversation_memories(id, world_id, npc_actor_id, player_actor_id, memory_type, content, source_kind, importance, created_tick, created_at)`.
- Allowed `memory_type`: `player_claim`, `preference`, `commitment`, `significant_interaction`.
- Allowed `source_kind`: `player_said`, `validated_event`.
- Add immutable `ConversationMemoryCandidate(memory_type, content)` to provider output.
- Persist only normalized, bounded candidates after validation; player claims always source as `player_said`.
- `DialogueContext` includes recent/high-importance pair-scoped conversational memories.

- [ ] Add failing schema/persistence/isolation tests.
- [ ] Confirm RED.
- [ ] Add schema and indexed pair lookup.
- [ ] Extend provider structured output with bounded memory candidates.
- [ ] Add validation: allow-list type, non-empty content, max 240 chars, max 2 candidates/turn, pair-scoped subject.
- [ ] Persist candidates transactionally with dialogue turn.
- [ ] Confirm another NPC cannot see private memories and re-instantiation preserves them.
- [ ] Confirm GREEN.

### Task 5: Open conversation threads and callbacks

**Files:**
- Modify: `src/samseberpg/db.py`
- Modify: `src/samseberpg/dialogue.py`
- Create: `tests/test_conversation_threads.py`

**Interfaces:**
- Add table `npc_player_conversation_state(npc_actor_id, player_actor_id, last_topic, open_threads_json, pending_question, last_seen_tick, turn_count, updated_at)`.
- Provider output gains nullable `open_thread` and `resolve_thread` plus `conversation_act`.
- Allowed conversation acts: `answer`, `ask`, `challenge`, `refuse`, `tease`, `observe`, `recall`, `redirect`.
- Thread text max 180 chars, maximum 3 open threads per pair.

- [ ] Add failing tests for opening a pending thread, leaving/rebuilding service, resuming it, resolving it, and cross-NPC isolation.
- [ ] Confirm RED.
- [ ] Add schema/state helpers and transactional persistence.
- [ ] Add thread state to `DialogueContext`.
- [ ] Extend provider schema and validation.
- [ ] Confirm GREEN.

### Task 6: Grounded NPC initiative

**Files:**
- Create: `src/samseberpg/conversation_initiative.py`
- Modify: `src/samseberpg/dialogue.py`
- Create: `tests/test_conversation_initiative.py`

**Interfaces:**
- Create immutable `ConversationInitiative(kind, cue)`.
- Create `resolve_initiative(...) -> ConversationInitiative | None` using only: pending thread, active concern involving player, important known fact/event since last seen, active request/consequence.
- Priority: pending thread > player-linked consequence > current request > important new known fact.

- [ ] Add failing deterministic priority tests.
- [ ] Confirm RED.
- [ ] Implement resolver without LLM calls or random lore.
- [ ] Add initiative cue to context and prompt; instruct provider it may lead with the cue naturally.
- [ ] Confirm GREEN.

### Task 7: Player Character Seed

**Files:**
- Modify: `src/samseberpg/db.py`
- Modify: `src/samseberpg/api.py`
- Modify: `src/samseberpg/dialogue.py`
- Modify: `web/src/main.ts`
- Modify: `web/src/api.ts` if needed
- Create: `tests/test_player_character_seed.py`
- Extend relevant web contract test.

**Interfaces:**
- Add table `player_character_seed(player_actor_id PRIMARY KEY, background_line_1, background_line_2, background_line_3, updated_at)`; character name remains authoritative in `actors.name`.
- Add read/write API for the current player seed with name validation 2–24 chars and exactly three non-empty lines, each <= 120 chars.
- `DialogueContext` receives player identity context as private model guidance, explicitly marked `NOT NPC KNOWLEDGE`.
- NPC known facts/memories do not include seed lines automatically.

- [ ] Add failing DB/API/privacy tests.
- [ ] Confirm RED.
- [ ] Add schema and API.
- [ ] Add minimal stream-safe startup form only when no seed exists; keep normal gameplay path intact after save.
- [ ] Add identity context to provider prompt with explicit non-knowledge rule.
- [ ] Confirm GREEN including browser contract/build.

### Task 8: Fallback v2 and repetition control

**Files:**
- Modify: `src/samseberpg/dialogue.py`
- Create or extend: `tests/test_living_npc_fallback.py`

**Interfaces:**
- Replace single generic fallback lines with deterministic state-aware pools selected from NPC/state/relationship/turn-count.
- Critical Stream Slice factual replies remain exact enough for acceptance tests.
- Avoid immediate identical fallback repetition for ordinary non-critical replies.

- [ ] Add failing tests showing repeated generic turns do not return identical text and state changes alter tone.
- [ ] Confirm RED.
- [ ] Implement small bounded pools, no random global state.
- [ ] Preserve existing critical road/wood/bread assertions.
- [ ] Confirm GREEN.

### Task 9: NPC Vitality automated acceptance

**Files:**
- Create: `tests/test_living_conversation_acceptance.py`
- Modify: `.github/workflows/stream-slice.yml`
- Modify: `.github/workflows/playable-candidate.yml`

**Interfaces:**
- Deterministic fake provider / context assertions cover: distinct voice payload, same-event different stance, private disclosure isolation, callback persistence, open thread, initiative, refusal act validation and no raw relation numbers in viewer-facing output.

- [ ] Add the focused acceptance suite.
- [ ] Add workflow steps so both focused Stream Slice and Playable Candidate gates execute it.
- [ ] Confirm focused and full Python suites pass.

### Task 10: Release verification and stream evidence

**Files:**
- Create: `docs/release/LIVING_CONVERSATION_V2.md`
- Extend browser route only if required to prove seed/callback flow.

**Verification:**
- Full Python suite.
- Living World acceptance.
- Living NPC acceptance.
- Social World acceptance.
- Stream Slice acceptance.
- Living Conversation v2 focused acceptance.
- Web contract tests.
- Production TypeScript/Vite build.
- Chromium stream route.
- Windows compatibility gate.
- SQLite integrity/reopen checks.

- [ ] Run exact-head CI on the final candidate.
- [ ] Inspect failing jobs/logs and fix any regressions.
- [ ] Record final SHA and run IDs in release doc / draft PR.
- [ ] Keep PR draft and unmerged pending separate integration authorization.
