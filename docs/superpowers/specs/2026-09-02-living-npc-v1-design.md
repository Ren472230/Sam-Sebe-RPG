# Living NPC v1 — Design

Status: proposed and grounded in the approved product direction (full RPG over a Living World).  
Branch: `feat/living-npc-v1`  
Base: `feat/autonomous-playtest-v1` @ `7bf5fe702f5211c1e8fe25d84a5bae2693b4e33f`

## 1. Product intent

`Sam-Sebe-RPG` is not primarily a quest-chain game. The target is a full RPG whose differentiator is a world that continues to live independently of the player and NPCs that can be spoken to naturally, remember relevant history, know only what they could plausibly know, and react to persistent world state.

Living NPC v1 must prove one concrete product hypothesis:

> A player can spend 10–15 minutes in the current village, freely talk to Oren, Mira and Kaspar, intervene in an autonomous world situation, leave/reload, and observe that the NPCs remain grounded in persistent state rather than behaving like three skins over one generic chatbot.

This milestone is about the social/world simulation core, not content volume.

## 2. Existing foundation we reuse

The current code already provides most of the deterministic substrate:

- Python/FastAPI authoritative game server;
- SQLite persistent world state;
- `GameService` canonical actions and idempotent event logging;
- Living World tick simulation with Mira/Kaspar autonomous resource behavior;
- `WAIT` and server-side `GIVE` support;
- multi-dimensional `relations` (`familiarity`, `trust`, `affinity`, `fear`, `conflict`, `romance`);
- `npc_memories` persistence;
- Oren-only `DialogueService` and OpenAI Responses provider with strict structured output and deterministic fallback;
- Phaser/TypeScript browser client;
- autonomous Playwright + backend playtest evidence from PR #38.

Living NPC v1 therefore generalizes an existing prototype instead of introducing a second AI/game-state architecture.

## 3. Scope

### In scope

1. Free-text dialogue with Oren, Mira and Kaspar.
2. NPC-specific personality/profile data.
3. NPC-scoped knowledge context rather than global omniscience.
4. Persistent dialogue history between each NPC and player.
5. Existing long-term `npc_memories` included in context.
6. Existing relation vector included in context.
7. NPC self/runtime state included in context.
8. Safe, narrow structured dialogue side effects.
9. Browser access to each NPC in the current vertical slice.
10. Player intervention in Mira/Kaspar wood situation using the already-authoritative `TAKE`/`GIVE` mechanics.
11. Deterministic fallback when the LLM is absent, malformed or unavailable.
12. Automated acceptance covering conversation, knowledge isolation, persistence and the world intervention loop.

### Explicitly out of scope

- Godot migration;
- combat;
- procedural quest generation;
- large map expansion;
- dozens of NPCs;
- NPC-to-NPC generated conversations;
- rumor propagation;
- autonomous LLM planning;
- voice input/output;
- LLM directly executing physical world mutations;
- global vector database / RAG system;
- automatic sentiment-driven relation changes.

Those belong to later Living NPC/Social World milestones.

## 4. Considered approaches

### A. Let the LLM own NPC state and actions

Fast to demo but rejected. It makes inventory, location, memories and consequences non-authoritative and difficult to test. Hallucinated facts become game state.

### B. Add generic chat only

Low risk, but rejected as the milestone goal. It would produce an AI chat box attached to the RPG while leaving conversation disconnected from the Living World.

### C. Authority-separated Living NPC — selected

Python remains authoritative. The LLM receives a bounded NPC context and returns natural language plus a tiny allow-listed structured proposal. The server validates any proposal and applies only permitted social/game transitions. This preserves the current deterministic architecture while enabling natural conversation.

## 5. Architecture

```text
Player text
   |
   v
Dialogue API
   |
   v
DialogueService
   |-- NPC profile
   |-- NPC current location/activity/runtime state
   |-- relation NPC -> player
   |-- high-value npc_memories
   |-- recent dialogue turns for this NPC/player pair
   |-- recent events caused by this NPC
   |-- actors/entities currently co-located with this NPC
   |-- NPC-specific domain state (e.g. Oren quest, Mira wood request)
   |
   v
DialogueProvider (OpenAI or deterministic fake/fallback)
   |
   +--> natural-language reply
   +--> allow-listed proposal(s)
                |
                v
         server-side validator
                |
                v
         permitted mutation only
                |
                v
 SQLite dialogue history / memories / canonical game state
```

The provider never receives unrestricted database access and never writes directly to the database.

## 6. NPC profiles

Introduce a small static profile module rather than a new editable content system in v1.

Each profile contains:

- `npc_id`;
- display name;
- role;
- short personality rules;
- speech style;
- stable motivations/concerns;
- explicit knowledge boundaries.

Initial profiles:

- **Oren** — measured innkeeper, observant, hospitable but guarded; concerned with keeping the tavern running.
- **Mira** — practical craftswoman, direct, dislikes wasted time; concerned with keeping her workshop productive.
- **Kaspar** — independent forager with dry humor; notices outdoor/resource conditions and dislikes being ordered around.

Profiles guide expression, not authoritative facts.

## 7. Knowledge model v1

The key rule is: NPCs do not receive the global `world_pulse` as universal knowledge.

A dialogue context may contain only:

1. **Self facts** — the NPC's own profile, location, activity and runtime state.
2. **Current perception** — actors/entities currently co-located with the NPC.
3. **Own actions** — recent `world_events` where `actor_id == npc_id`.
4. **Relationship** — existing relation row from this NPC to the player.
5. **Long-term memory** — top relevant `npc_memories` for this NPC/player.
6. **Conversation memory** — recent persisted dialogue turns with this same NPC/player.
7. **NPC-specific authoritative state** — e.g. Oren's quest state; Mira's `requested_wood`/`wood_stock`; Kaspar's goal/carrying state.

V1 does not infer that one NPC knows an event solely because another NPC knows it. Cross-NPC information transfer is reserved for Social World v1.

## 8. Persistent dialogue history

Add a `dialogue_turns` table:

- `id`;
- `world_id`;
- `npc_actor_id`;
- `player_actor_id`;
- `user_text`;
- `npc_text`;
- `proposal_json`;
- `used_fallback`;
- `created_at`.

Every successful dialogue call writes one turn after a response is validated/fallback-resolved.

Context includes only the most recent bounded window for the same NPC/player pair (v1 target: 6 turns). This gives immediate conversational memory without introducing embeddings or summarization.

`npc_memories` remains the durable high-value memory store for canonical important facts (quest completion, validated commitments, later social facts).

## 9. Dialogue API compatibility

Existing callers must keep working.

`POST /api/dialogue` evolves from Oren-only to:

```json
{
  "player_id": "player-id",
  "npc_id": "npc_mira",
  "text": "Что случилось?"
}
```

`npc_id` defaults to `npc_oren` for backwards compatibility during this milestone.

The response remains compatible with the current fields and is extended rather than replaced:

```json
{
  "npc_id": "npc_mira",
  "text": "...",
  "proposal": null,
  "social_action": null,
  "used_fallback": false
}
```

The existing Oren quest proposal remains supported.

## 10. Safe dialogue side effects

V1 intentionally allows very little mutation from generated dialogue.

### Physical actions

The LLM cannot directly move an actor, create/remove items, transfer currency, complete quests or alter Living World runtime state.

Those continue through existing authoritative actions/services.

### Social memory action

V1 adds one narrow validated social action for the target slice:

`remember_commitment:bring_useful_wood_to_mira`

It may be accepted only when:

- current NPC is Mira;
- Mira currently has `requested_wood == true`;
- the provider explicitly classified the player's utterance as a commitment;
- the player/NPC identities exist.

The applied mutation is a normalized Mira memory about what she understood the player to have promised. It does not create wood or mark the world problem solved.

This is deliberately a **belief/social memory**, not a physical world fact. The physical consequence occurs only when the player later obtains `driftwood_1` and executes canonical `GIVE` to Mira.

No automatic relation-number mutation is added in v1.

## 11. Deterministic fallback

Provider failure must not make NPC interaction unusable.

Fallback is NPC/state-aware:

- Oren keeps current quest-aware behavior;
- Mira comments on work/request state;
- Kaspar comments on his current goal/carrying/location state.

Fallback uses only authoritative context and writes normal dialogue history with `used_fallback = true`.

## 12. Browser UX

The current Phaser client is retained.

### DialoguePanel

Refactor `openOren()` into a generic NPC dialogue panel:

- NPC name/title;
- conversation transcript;
- free-text input;
- send button;
- close button;
- existing contextual Oren quest buttons retained where valid;
- no fake prewritten player-choice tree.

### Accessing NPCs

For v1, use the existing World Pulse/HUD as the minimum reliable interaction surface rather than building new maps/scenes:

- list currently co-located NPCs with `Поговорить` actions;
- expose canonical adjacent-location travel controls from server state;
- keep TavernScene's Oren interaction as a shortcut;
- expose current Mira/Kaspar intervention actions when canonical preconditions are met.

This is intentionally temporary UI infrastructure for proving the Living NPC loop. It avoids blocking the core experiment on visual-production work.

### Mira/Kaspar intervention

The browser client exposes existing canonical capabilities needed for the slice:

- `MOVE` to connected locations;
- `TAKE driftwood_1` at the river when available;
- `GIVE driftwood_1 -> npc_mira` when co-located and valid;
- `WAIT` remains available to let the autonomous world progress.

## 13. Primary playable acceptance route

The target autonomous route is:

1. Start a fresh world/player.
2. Advance world time until Mira requests wood.
3. Move to Mira and open free dialogue.
4. Ask what is wrong; verify the dialogue context contains Mira's real request/runtime state.
5. Tell Mira the player will help; validated social commitment is persisted.
6. Move to the river while Kaspar is also responding to the world problem.
7. Take the shared `driftwood_1` before Kaspar does.
8. Return to Mira and execute canonical `GIVE`.
9. Talk to Mira again; her context now contains both the prior conversation/commitment and the updated resolved world state.
10. Reload the browser/server state and verify the conversation history/social memory/world consequence persist.
11. Talk to Kaspar and verify he was not given the private Mira/player conversation as knowledge.

Alternate route:

- do not intervene;
- advance time;
- verify Kaspar independently resolves Mira's request;
- NPC dialogue reflects the resulting state.

## 14. Tests and verification

Implementation is test-driven.

### Backend unit/contract tests

- generic Oren/Mira/Kaspar context construction;
- unknown/inaccessible NPC rejection;
- NPC-specific runtime state;
- relation vector isolation;
- recent dialogue history persistence and bounded retrieval;
- no cross-NPC private conversation leakage;
- malformed/forbidden provider output falls back safely;
- only allow-listed social action can be applied;
- commitment validation requires Mira's active wood request;
- existing Oren quest dialogue remains backward compatible.

### API tests

- `npc_id` request handling;
- backwards-compatible Oren default;
- response schema;
- dialogue persistence across fresh service instances;
- invalid NPC/location returns deterministic client-visible error.

### Web contract tests

- generic dialogue API payload;
- `GIVE` + `recipient_id` support;
- travel options mapping;
- no hard dependency on a live OpenAI key for automated tests.

### End-to-end/autonomous playtest

Extend the PR #38 evidence route with the primary Living NPC path and alternate no-intervention path. Capture browser/console errors and a final report.

The milestone is green only if:

- all existing backend tests remain green;
- Living World acceptance remains green;
- web typecheck/build/contract tests remain green;
- autonomous browser route passes without unexpected client/backend errors;
- private dialogue knowledge isolation is explicitly asserted;
- persistence survives reload/re-instantiation.

## 15. Implementation boundaries

Prefer focused additions over a rewrite:

- `src/samseberpg/dialogue.py` — generic orchestration, kept small;
- new `src/samseberpg/npc_profiles.py` — static v1 profiles;
- `src/samseberpg/db.py` — `dialogue_turns` schema only;
- `src/samseberpg/api.py` — generic dialogue request/response plus minimal travel projection;
- existing Living World/GameService remain authoritative; no duplicate simulation layer;
- `web/src/api.ts` — generic dialogue, `GIVE`, travel projection;
- `web/src/ui/DialoguePanel.ts` — generic free-text conversation;
- current World Pulse/HUD — talk/travel/intervention controls;
- tests added beside existing dialogue/API/web/playtest suites.

Do not restore PR #35 wholesale. Reuse only validated ideas or narrowly port code that still matches the current architecture.

## 16. Success criterion

Living NPC v1 succeeds when the current tiny village demonstrates this behavior without manual database manipulation:

> The world develops independently; the player can ask three different NPCs about their current circumstances in free text; each answers from its own bounded knowledge/personality/history; a conversation can create a validated social commitment; the player can fulfill or ignore it through canonical gameplay; both the social and world consequences survive reload; another NPC does not magically know the private conversation.

If this is convincing, the next milestone should be Social World v1 / Living NPC v2 (NPC decisions and information transfer), not another hand-authored quest chain.
