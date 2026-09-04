# Stream Slice v1 - One Session in the Village

Date: 2026-09-04
Status: design approved in chat; written spec pending user review
Target branch: feat/stream-slice-v1
Base: latest verified feat/social-world-v1 head

## 1. Product goal

Prepare Sam-Sebe-RPG for a roughly one-hour live stream whose main entertainment value is the core product idea:

- NPCs feel like persistent people rather than disposable chat windows;
- ordinary village life gives the player concrete things to do;
- player promises and actions change later conversations;
- NPCs can learn facts from one another only through grounded causal contact;
- the village hints at a larger fantasy world without requiring a large content build.

The stream is also a product test. A successful session should be watchable even by people who are not already invested in development details.

## 2. Success statement

By the end of one fresh session, a streamer should be able to truthfully summarize the experience as:

"I spent an hour in this village. I met people, promised things, helped or ignored them, watched them act without me, saw one person learn something from another, met a traveler carrying news from outside the village, and later conversations reflected what happened earlier."

The build is a streamable vertical slice, not a claim that the full RPG is complete.

## 3. Existing foundation to preserve

Stream Slice v1 builds on the current stack instead of replacing it:

- Python/FastAPI + SQLite authoritative backend;
- Phaser/TypeScript/Vite frontend;
- canonical MOVE / TAKE / GIVE / WAIT actions;
- Living World tick simulation;
- Living NPC free-text dialogue with bounded context and deterministic fallback;
- Social World npc_knowledge provenance and NPC-to-NPC causal knowledge transfer;
- existing Playwright browser evidence and Windows gates.

Existing content already covers more of the approved stream design than first assumed:

- Oren is already the innkeeper;
- tavern_interior is already The Wayfarer's Hearth;
- Mira, Kaspar, Oren already have distinct profiles and schedules;
- bread_loaf_1 already exists in Village Square;
- the wood problem already creates a player-vs-autonomous-NPC branch.

Therefore v1 will NOT add a second innkeeper or a second guest-house location. The existing tavern becomes the guest-house / traveler hub.

## 4. Scope

### 4.1 Persistent cast

Keep the current three persistent NPCs:

1. Mira - craftswoman; practical, direct, values concrete help.
2. Kaspar - forager; independent, dry humor, reacts to what he actually knows.
3. Oren - innkeeper; social anchor at The Wayfarer's Hearth.

Add exactly one temporary visitor:

4. npc_wayfarer_1 - a named wayfarer with one concise personality, one outside-world fact, and a limited session presence.

The wayfarer is intentionally low-lore. The first stream slice must not invent major canonical nations, wars, religions, or political history that could conflict with later Zodiac/world canon.

### 4.2 Locations

Reuse only current locations:

- Workshop Yard;
- Village Square;
- River Edge;
- The Wayfarer's Hearth (existing tavern_interior).

No new gameplay scene is required for v1.

### 4.3 Household loops

The stream needs two concrete physical loops, not a large quest catalog.

#### Loop A - Mira's workshop wood

Preserve the existing loop:

- Mira runs out of useful wood;
- player can promise to help;
- player can fetch the driftwood personally OR do nothing;
- Kaspar can solve it autonomously;
- if Kaspar physically delivers to Mira, social knowledge and Mira -> Kaspar relation effects occur;
- Kaspar can later mention what Mira told him about the player's promise.

This remains the primary proof of Living World + Living NPC + Social World working together.

#### Loop B - Oren's hospitality supply

When the wayfarer arrives, Oren needs one existing loaf of bread from Village Square for the guest.

Rules:

- use bread_loaf_1 already present in the database;
- the request is optional and time-insensitive inside the session;
- player can TAKE the loaf and GIVE it to Oren;
- successful delivery updates Oren runtime state so later dialogue can acknowledge the help;
- ignoring the request is valid and does not block the rest of the stream;
- no new inventory subsystem, crafting system, currency rule, or quest framework is introduced.

The point is variety in everyday life, not a second traditional quest system.

## 5. Wayfarer / outside-world beat

The temporary wayfarer is the cheapest way to make the village feel connected to a larger world.

### 5.1 Arrival

The wayfarer begins absent from visible locations.

After a deterministic world threshold in a fresh stream session, the Living World creates a canonical arrival event and places the wayfarer in The Wayfarer's Hearth.

The exact threshold should be late enough that the streamer has time to meet Mira/Kaspar first, but early enough that the visitor reliably appears during a normal one-hour session. The implementation plan should target a threshold around the first completed wood beat or a bounded tick threshold, whichever happens first.

### 5.2 News

The wayfarer brings one grounded, low-lore external fact such as a damaged road, delayed caravan, unusual weather, or another mundane travel condition.

Requirements:

- the fact is persisted in npc_knowledge;
- source/provenance identifies the wayfarer;
- Oren can learn it through the canonical arrival/contact event;
- other NPCs do not magically know it;
- dialogue may render the fact naturally but cannot invent additional external facts as canonical state.

### 5.3 Optional later contact

If the simplest implementation can move the wayfarer to Village Square later without destabilizing schedules, a second grounded contact may let another NPC learn the news. This is optional for v1. The required proof is wayfarer -> Oren plus the existing Mira -> Kaspar transfer.

## 6. Dialogue experience

Free-text dialogue is the main stream interaction surface.

### 6.1 Required behavior

Each NPC receives only bounded, NPC-scoped context:

- profile / speech style / motivations;
- current activity and location;
- relation to player;
- relevant personal memories;
- known facts with provenance;
- recent player dialogue;
- nearby actors/entities;
- recent own events;
- relevant runtime state.

The model writes language only. Canonical facts, inventory, movement, relations, requests, and world events remain server-controlled.

### 6.2 Stream robustness

Live model calls must be bounded:

- explicit request timeout;
- at most one short retry if appropriate;
- deterministic fallback on timeout, provider failure, invalid structured output, or missing API key;
- no player action may remain stuck waiting indefinitely for the model.

The exact current OpenAI Python client timeout/retry API must be verified against current official documentation during implementation before changing provider configuration.

### 6.3 Fallback quality

Fallback dialogue must cover the stream-critical beats rather than only generic greetings:

- Mira before/after wood resolution;
- Mira commitment acknowledgment;
- Kaspar before/after learning Mira's report;
- Oren before/after bread delivery;
- Oren after learning the wayfarer's news;
- the wayfarer's own short news explanation.

This ensures the stream can continue if live AI fails.

## 7. Stream UI

The UI should optimize readability for a viewer, not expose backend internals.

### 7.1 Keep

- current scene/gameplay view;
- free-text dialogue panel;
- nearby talk buttons;
- MOVE / TAKE / GIVE / WAIT controls;
- World Pulse concept.

### 7.2 Add / adjust

A stream presentation mode should show a compact human-readable layer:

- current world step/session phase;
- nearby NPC names;
- concise current activity for Mira/Kaspar/Oren/wayfarer when relevant;
- last 3-5 meaningful public world events.

Examples:

- "Mira needs wood for the workshop"
- "Kaspar headed toward the river"
- "Kaspar brought wood to Mira"
- "A traveler arrived at The Wayfarer's Hearth"
- "Oren is looking for bread for a guest"

Do not show raw trust numbers, JSON, event IDs, source_knowledge_id, or internal result codes to the audience.

If a relation change is surfaced, phrase it in human language, for example:

- "Mira trusts Kaspar a little more."

### 7.3 Legacy UI clutter

In stream presentation mode, legacy quest/coin/trust text that distracts from the Living World story should be hidden or visually de-emphasized. Existing non-stream behavior must remain compatible.

The preferred mechanism is a frontend stream-mode flag/query parameter rather than forking the whole client.

## 8. Stream session launcher and reset

A stream build must be repeatable.

### 8.1 Isolated database

Use a dedicated stream database such as:

`data/stream-slice.sqlite3`

A fresh stream reset must not touch developer/test/player databases.

### 8.2 Deterministic start

The stream launcher should use a fixed game starting clock/context suitable for existing schedules, independent of the real wall-clock start time. This avoids a 3 PM stream and a 10 PM stream producing fundamentally different opening positions.

This is a stream-session concern, not a rewrite of the global time architecture.

### 8.3 One-command operation

Provide a simple documented launch/reset path suitable for Windows. Preferred end state:

- one reset command;
- one start command or PowerShell launcher;
- clear localhost URL;
- optional public-tunnel helper only if it can be added without making the critical path fragile.

Remote hosting/tunneling is convenience scope, not required for the core mechanics acceptance.

## 9. Event and data model additions

Keep additions narrow.

Expected additive concepts:

- seeded temporary wayfarer NPC/profile;
- wayfarer presence/session state, ideally via existing npc_runtime_state;
- Oren hospitality state via existing npc_runtime_state;
- a small number of new canonical world event types if required, for example WAYFARER_ARRIVED and WAYFARER_DEPARTED;
- one shareable wayfarer news fact in npc_knowledge;
- no new general quest engine;
- no new global rumor bus;
- no new combat/economy/crafting subsystem.

If existing world_events event_type has no DB check constraint, new event names remain additive at persistence level.

## 10. Error handling and safety

- Stream reset is explicit and isolated.
- Re-running the same world threshold must not duplicate the wayfarer arrival/news.
- Reload preserves current stream state.
- Repeated dialogue does not duplicate knowledge facts.
- Provider errors degrade to fallback, not HTTP 500 for normal dialogue use.
- A failed Social World processor must preserve transaction atomicity.
- No stream-only code may silently mutate main/prod databases.

## 11. Acceptance gate

### 11.1 Backend acceptance

A fresh stream session must prove:

1. Player starts in the expected deterministic opening state.
2. Mira eventually requests wood.
3. Player can promise Mira help.
4. Kaspar does not know that promise before contact.
5. Player can either solve the wood problem or let Kaspar solve it.
6. On Kaspar -> Mira delivery contact, Mira/Kaspar social consequences persist.
7. Kaspar later knows the player's promise with Mira provenance.
8. Wayfarer arrives exactly once.
9. Oren learns the wayfarer's external news through grounded contact.
10. Mira/Kaspar do not know that news without a grounded route.
11. Oren's bread request becomes available after wayfarer arrival.
12. Player can deliver bread using existing TAKE/GIVE semantics.
13. Oren's later dialogue reflects whether bread was delivered.
14. Reload preserves world, knowledge, relations, hospitality state, and wayfarer presence.
15. Duplicate WAIT/replay paths do not duplicate arrivals, news, or requests.

### 11.2 Browser acceptance

A dedicated Playwright route must cover the audience-readable critical path:

- opening state;
- Mira conversation and promise;
- Kaspar pre-contact ignorance;
- autonomous delivery;
- Kaspar post-contact provenance-aware line;
- wayfarer visible in tavern;
- traveler news conversation;
- Oren hospitality request;
- bread TAKE/GIVE;
- Oren post-delivery acknowledgment;
- reload persistence;
- zero page errors / console errors.

Store screenshots at major beats and retain trace/video on failure.

### 11.3 Soak / preflight

Before calling the slice stream-ready, automate:

- full Python suite;
- web contract suite;
- production build;
- canonical Chromium route;
- Living NPC Chromium route;
- Social World Chromium route;
- Stream Slice Chromium route;
- Windows compatibility;
- a deterministic multi-tick soak covering the whole stream session state machine;
- SQLite integrity/reopen check.

A separate optional live-provider preflight may test a small number of real model calls when an API key is present, but CI must remain capable of passing without a live key.

## 12. Out of scope

Do not add for Stream Slice v1:

- 15 NPCs;
- combat;
- skill trees;
- loot progression;
- multiple settlements;
- season simulation;
- full offline world catch-up;
- procedural quest generation;
- global free-form NPC-to-NPC LLM conversations;
- a second innkeeper;
- a second guest-house scene;
- Godot or Ren'Py migration;
- a major visual redesign.

## 13. Implementation order

Critical path after spec approval:

1. finish and verify Social World browser gate;
2. create feat/stream-slice-v1 from verified Social World head;
3. TDD wayfarer/Oren runtime and arrival idempotency;
4. TDD wayfarer news knowledge/provenance;
5. TDD Oren bread request and delivery using existing bread_loaf_1;
6. expand stream-critical fallback dialogue;
7. add bounded live-provider timeout/retry after current official API verification;
8. add stream presentation mode;
9. add isolated reset/start launcher;
10. backend acceptance;
11. Playwright Stream Slice route;
12. full release/Windows/soak verification;
13. only then prepare a human one-hour stream runbook.

## 14. Definition of done

Stream Slice v1 is done only when:

- the automated critical route is green;
- the existing Living World / Living NPC / Social World routes stay green;
- reset and replay are deterministic;
- the browser presentation makes causal changes understandable without developer commentary;
- live dialogue failure cannot stall the session indefinitely;
- a fresh build can sustain the intended sequence of interactions without manual database edits;
- no merge into main occurs without separate explicit user authorization.
