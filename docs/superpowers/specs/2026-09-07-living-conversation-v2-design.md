# Living Conversation v2 — Design

Status: approved in chat for autonomous implementation  
Branch: `feat/living-conversation-v2`  
Base: `15db52d9e63bb97c4aeecb15744abac09f2d4b2f`

## 1. Product goal

Make existing NPC conversations feel like interactions with distinct people who have their own temperament, current mood, concerns, opinions, memory, unfinished business and willingness to engage, while preserving the current authoritative Living World / Social World architecture.

The target stream experience is that after 10 minutes of conversation a player can describe an NPC as a person (for example, “Каспар немного мудак, но прикольный”) rather than as a gameplay function or a generic chatbot persona.

## 2. Architecture choice

Keep the current authority separation:

- Python/FastAPI + SQLite remain authoritative for world facts, location, inventory, relations, world events and side effects;
- the LLM receives bounded NPC-scoped context and writes language plus narrow allow-listed conversational metadata;
- the LLM must not directly mutate physical world state or convert player claims into objective facts;
- Social World provenance and private-knowledge boundaries remain intact.

Living Conversation v2 adds a conversation layer above the existing `DialogueService` rather than replacing it.

## 3. Conversation context layers

A generated reply is driven by:

1. authoritative NPC knowledge and perception;
2. static voice/personality profile;
3. resolved current inner state;
4. relationship behavior mode;
5. recent pair-scoped dialogue;
6. durable pair-scoped conversational memories;
7. unresolved conversation threads;
8. current conversational intent / initiative trigger;
9. optional player character identity context that is private to the player model until causally revealed.

## 4. Voice Bible

Extend `NpcProfile` for Oren, Mira, Kaspar and Talen with:

- values;
- temperament;
- humor style;
- likes/dislikes;
- conversation preferences;
- avoided topics;
- behavior under trust/distrust/conflict;
- signs of warmth;
- characteristic phrasing;
- forbidden chatbot-like phrasing;
- default reply length.

Profiles guide expression only. They do not create world facts.

## 5. Anti-chatbot behavior

The provider instruction must explicitly discourage:

- repeating the player’s question;
- opening with generic empathy such as “понимаю” without reason;
- “интересный вопрос” and assistant-like service language;
- bullet lists / structured option menus in ordinary speech;
- explaining the NPC’s own personality;
- always agreeing;
- always being helpful;
- ending every reply with a question;
- long literary monologues when a short reply fits.

The provider may instead use short answers, pauses, disagreement, counter-questions, refusal, mild misunderstanding, dry humor and topic changes when consistent with profile/state.

## 6. Inner state

Introduce deterministic `NpcConversationStateResolver` that derives a compact conversation state from authoritative data.

Target fields:

- `mood`;
- `secondary_mood`;
- `current_concern`;
- `current_desire`;
- `availability`.

No LLM call is used to determine these fields. The resolver reads existing runtime state, current activity, recent world events and relationship state.

V2 only needs rules for the four stream NPCs and the existing Stream Slice situations.

## 7. Subjective stance

NPCs may hold a subjective stance toward known facts without changing the fact itself.

Examples for the wayfarer road news:

- Oren: worries about tavern supplies and stranded travelers;
- Mira: worries about delayed materials;
- Kaspar: distrusts village dependence on caravans;
- Talen: is irritated when doubted because he saw the road himself.

Stances are static/profile-driven or deterministic from known facts and state. They are not global canon.

## 8. Conversational memory

Persist pair-scoped conversational memories with explicit provenance.

Supported memory classes for v2:

- `player_claim` — what the player said about themselves;
- `preference` — stated like/dislike;
- `commitment` — an understood promise;
- `significant_interaction` — validated social event worth recalling.

A player utterance such as “я король” may only become “player claimed to be king”, never an objective world fact.

The LLM may propose memory candidates; the backend validates type, subject, source and length before persistence.

## 9. Conversation thread state

Persist pair-scoped conversation state containing:

- `last_topic`;
- `open_threads`;
- `pending_question`;
- `last_seen_tick`;
- `turn_count`.

Open threads let NPCs naturally resume unfinished exchanges after the player leaves and returns.

The provider may propose opening or resolving a thread, but the backend owns storage and validation.

## 10. NPC initiative

On conversation open or normal reply, the backend may surface one initiative trigger when grounded by current state:

- unresolved thread;
- important event since last meeting;
- active concern involving the player;
- meaningful relationship change;
- current request or consequence.

NPC initiative must be causally grounded. No random unrelated lore injection.

## 11. Relationship behavior

Map the existing relation vector into a small derived behavior mode such as:

- `guarded`;
- `neutral`;
- `comfortable`;
- `warm`;
- `distrustful`;
- `hostile`.

The numeric relation row remains authoritative. The derived mode only changes conversational behavior and phrasing.

The player should hear relationship changes through tone and behavior rather than raw trust numbers or explicit “I trust you X%”.

## 12. Player Character Seed

Before a fresh stream game, support:

- character name;
- exactly three background lines.

This is the player’s own identity context and does not become NPC knowledge automatically.

NPCs learn details only when the player reveals them or a grounded Social World route transmits them.

V2 backend must be able to store this seed; a minimal browser form may be added if doing so does not destabilize the stream path.

## 13. Provider output contract

Extend generated dialogue metadata narrowly. Target response fields:

- `text`;
- existing `proposal`;
- existing `social_action`;
- `conversation_act`;
- `memory_candidates`;
- `open_thread`;
- `resolve_thread`.

All metadata is validated server-side. Unknown values or invalid side effects fall back safely.

## 14. Fallback v2

Fallback remains mandatory and deterministic but must avoid obvious repetition.

Use small state-aware pools keyed by:

- NPC;
- inner state / situation;
- relationship behavior;
- recent repetition count.

Fallback must still preserve factual correctness and critical Stream Slice beats.

## 15. Acceptance: NPC Vitality Gate

Living Conversation v2 is stream-ready only if all of the following pass.

### Blind identity

Given anonymous generated lines from the four NPCs, a reviewer can identify the correct speaker in at least 8/10 representative cases.

### Same event, different person

The same grounded fact produces meaningfully different reactions from Oren, Mira, Kaspar and Talen.

### Privacy

A player self-disclosure to one NPC is not known by another NPC without a grounded transfer route.

### Callback

An important player disclosure or promise can be recalled naturally after later turns / world progression.

### Open thread

A conversation interrupted after a pending question can resume later with the NPC referencing the unresolved point.

### Initiative

At least one stream-critical conversation can begin or change direction from a grounded NPC initiative rather than pure player Q&A.

### Refusal / disagreement

NPCs can refuse, challenge or avoid a topic when personality, state or relationship makes that appropriate.

### Anti-bot

Representative 10-minute transcripts must avoid assistant-like filler, repetitive service language, constant agreement and constant question-ending.

### Existing safety

All existing Living World, Living NPC, Social World and Stream Slice acceptance tests remain green; private knowledge isolation, persistence and authoritative world mutations remain unchanged.

## 16. Scope exclusions

Do not add:

- vector database / embeddings / RAG;
- autonomous LLM planning;
- background LLM calls every tick;
- free-form NPC-to-NPC LLM conversations;
- dynamic lore generation;
- procedural quests;
- dozens of emotion dimensions;
- separate AI model per NPC;
- broad psychology simulation.

## 17. Definition of done

Living Conversation v2 is done when the four existing stream NPCs are reliably distinct, stateful, opinionated, capable of initiative/refusal/callbacks, remain causally grounded in their own knowledge, preserve current game authority boundaries, and pass both automated regression checks and the dedicated NPC Vitality acceptance suite.

No merge into main or any integration branch occurs without separate explicit user authorization.