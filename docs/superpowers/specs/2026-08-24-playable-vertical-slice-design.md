# Playable Vertical Slice — Design Specification

Date: 2026-08-24
Target release candidate: 2026-08-30
Internal playable deadline: 2026-08-28

## Goal

Ship the first genuinely playable graphical vertical slice of Sam-Sebe-RPG / Emergent RPG / Living World.

The slice must prove one complete causal loop:

`start village -> enter tavern -> talk to Oren -> accept bring-5-firewood quest -> collect real items -> return -> deterministic turn-in -> reward/relationship/memory change -> Oren reacts differently -> restart preserves the consequence`.

The goal is not to prove every Living World system. One finished mechanic is more valuable than many partial systems.

## Existing implementation to preserve

The current repository already contains a verified Python shared-world kernel. It is not throwaway R&D.

Keep these existing foundations as authoritative:
- Python 3.12 package under `src/samseberpg`;
- SQLite canonical state;
- `GameService` as the mutation/read boundary;
- typed `CanonicalAction` / `ActionResult` / `WorldView` models;
- deterministic LOOK, MOVE, TAKE, DROP;
- atomic state mutation + `ActionEvent` persistence;
- idempotency by external interaction ID;
- restart persistence;
- `SystemClock` / `FakeClock`;
- lazy deterministic NPC schedule catch-up;
- concurrency-safe writes with `BEGIN IMMEDIATE`;
- existing tests and scripted shared-world proof.

Do not move canonical world state into JavaScript and do not let the LLM write SQLite directly.

## Visual canon

Visual R&D is closed. Production follows MASTER STYLE REFERENCE v1:
- 2.5D cardboard theatre / diorama;
- large readable forms and handmade miniature feel;
- decorative world with more volumetric sky;
- milk/graphite base;
- turquoise as a visible signature color;
- scarlet + black cultural accents;
- amber for warm light/fire;
- restrained Udmurt and Armenian motifs;
- no neural-detail scatter.

The old ASCII/textmode visual direction is archived and is not the renderer for this slice.

## Architecture

```text
Browser Game Client
Phaser + TypeScript
        |
        | JSON HTTP
        v
Thin Python Web Adapter
        |
   +----+------------------+
   |                       |
   v                       v
GameService            DialogueService
(existing core)        (new LLM adapter)
   |                       |
   |                   read-only context
   |                       |
   +-----------+-----------+
               v
        Canonical SQLite
               |
     state + ActionEvent
```

### Rule of authority

Only deterministic Python application logic may mutate canonical state.

The browser may request actions. The LLM may propose an allowed intent. Neither may directly update canonical tables.

## Game client

Add a browser client under a dedicated frontend directory.

Recommended stack:
- TypeScript;
- Vite;
- Phaser 3.x for the production sprint;
- static raster layers supplied by Visual Production.

P0 scenes:
1. `VillageScene`;
2. `TavernScene`.

P0 client features:
- launch screen / start action;
- player movement;
- camera;
- collision rectangles;
- interaction hotspots;
- parallax-ready layer structure;
- village -> tavern transition;
- dialogue panel;
- quest status;
- small inventory count for firewood;
- visible error/fallback message if LLM is unavailable.

Player pixel coordinates are presentation state for this slice. Canonical world state stores logical location, inventory and consequences. Scene transitions and item interactions call authoritative Python actions.

## Python web adapter

Add the smallest practical HTTP adapter around the existing core. It must not duplicate game rules.

Required endpoints/capabilities:
- create/load local player session;
- observe current canonical world state required by the client;
- execute canonical gameplay action;
- request NPC dialogue;
- accept/turn in the single quest through deterministic application logic;
- serve or support the built frontend during local play.

A local adapter may map the single graphical player to a stable synthetic external identity while preserving the existing player model. Do not perform a risky identity/schema rewrite solely for this sprint.

## Village and locations

Reuse the existing village world instead of replacing the bootstrap wholesale.

Add only what the playable route requires:
- a logical tavern interior location;
- adjacency between village and tavern;
- Oren placed/scheduled so he is reliably available for the acceptance path;
- five or more portable firewood entities accessible to the player.

The graphical village may visually contain more landmarks than there are canonical navigation nodes. Pixel movement is not the same as canonical location movement.

## Quest system

Implement one quest template only:

`bring_5_firewood`

Required states:
- `available`;
- `active`;
- `completed`.

Required deterministic transitions:
1. Oren can offer the quest only when it is available.
2. Acceptance creates/persists the active quest state.
3. Firewood acquisition is represented by real canonical items owned by the player; reuse TAKE where practical.
4. Turn-in validates ownership/count in canonical state.
5. Invalid turn-in does nothing except return a typed failure.
6. Valid turn-in atomically consumes or transfers the required firewood, completes the quest, grants the reward, changes relationship state, records the event and creates the persistent memory.
7. Repeated turn-in cannot duplicate reward or relationship changes.

Do not build a procedural quest generator for this slice.

## Relations

Reuse the existing `relations` schema reserved by the shared-world kernel.

For P0, one visible value is enough, e.g. Oren -> player trust/familiarity.

Successful quest completion must increase a relation value deterministically. The exact balancing number is configuration/content, not LLM output.

## NPC memory

Add minimal persistent NPC memory sufficient to prove consequence.

A memory record needs at least:
- NPC actor ID;
- player actor ID or subject reference;
- compact fact/summary;
- timestamp;
- importance;
- reinforcement count or equivalent field.

P0 proof memory:
`The player brought Oren the requested firewood.`

The post-quest dialogue context must contain this memory after restart.

### Law of Forgetting

The full forgetting model is P1, not a P0 blocker.

Minimal P1 selection rule:
- important memories outrank weak ones;
- recent memories outrank old ones;
- reinforced memories decay more slowly;
- old weak memories can simply stop entering the LLM context without being physically deleted.

## Dialogue / LLM layer

Implement `DialogueService` as an adapter, not a world authority.

For Oren it receives a constrained context assembled from canonical state:
- identity and role;
- personality/content profile;
- current logical location/activity;
- relevant local knowledge;
- current relationship with the player;
- quest state;
- relevant persistent memories;
- a short recent dialogue window.

The model returns:
- NPC text;
- optionally one structured proposal from a small allowlist such as `offer_quest: bring_5_firewood`.

Application logic validates every proposal before any state change.

The LLM must never be trusted to invent inventory, money, quest completion, rewards, memories or relation mutations.

## LLM failure behavior

The slice must remain completable when the LLM request fails or is unavailable.

For the critical quest beats, provide deterministic fallback dialogue for:
- first greeting;
- quest offer;
- active-quest reminder;
- insufficient-firewood turn-in;
- successful turn-in;
- post-quest acknowledgement.

This is a release requirement, not optional polish.

## Real time

The existing Clock + lazy NPC catch-up implementation remains part of the core and should stay green.

Do not add continuous ticking or a background simulation service.

For P0, Oren's schedule must not make the acceptance route unavailable at arbitrary test time. More expressive schedules are P1.

Morning newspaper/digest is P2 for this release.

## Persistence

The existing SQLite database remains authoritative.

The vertical slice must preserve across full process restart:
- player actor;
- logical location as applicable;
- inventory ownership;
- quest state;
- relationship change;
- NPC memory;
- action/event history.

Client-only presentation coordinates do not need persistence for P0.

## Content ownership between workstreams

### MASTER / Project Control
Owns scope, gates, architecture decisions, P0/P1/P2 and acceptance.

### Visual Art Direction / Production
Produces game-ready village/tavern layers, player/NPC sprites or cutouts, firewood/interaction assets and minimal dialogue/UI skin. It does not reopen art direction.

### Game Core / Build & Integration
Owns repository implementation, web adapter, Phaser client, core extensions, quest lifecycle, persistence integration, LLM integration, tests and build.

### NPC / World Systems & Content
Owns Oren's personality/knowledge/content data, quest copy, memory wording, constrained dialogue policy and test conversations. It does not create a second engine.

## P0 implementation order

1. Verify existing Python tests remain green.
2. Add a minimal web adapter that can observe and execute existing core actions.
3. Add browser client boot + greybox VillageScene.
4. Connect local player/session to canonical observation.
5. Add TavernScene and authoritative village/tavern transition.
6. Add firewood entities and inventory collection through the core.
7. Add deterministic single-quest persistence and turn-in.
8. Add relationship and memory consequence.
9. Add Oren dialogue context + structured LLM proposal path.
10. Add deterministic dialogue fallback.
11. Integrate production visual assets.
12. Run end-to-end restart acceptance repeatedly.

## Internal gates

### 24 Aug
Game architecture frozen; existing kernel verified; adapter/client skeleton started.

### 25 Aug
Graphical village movement, tavern transition and canonical persistence connected.

### 26 Aug
Oren dialogue works from real state with fallback.

### 27 Aug
`bring_5_firewood` works end to end through deterministic state.

### 28 Aug
Relationship + memory + post-quest reaction survive restart. First complete playable slice.

### 29 Aug
QA only: repeated runs, malformed/failed LLM, duplicate interactions, save/restart, quest exploits and blockers.

### 30 Aug
Feature freeze, final visual integration, clean-start acceptance and release candidate.

## P1 after the loop is green

- more polished parallax;
- second NPC;
- lightweight Law of Forgetting ranking;
- richer elapsed-real-time reactions;
- ambient audio;
- quest journal polish;
- small NPC animation;
- additional world reaction after quest.

## P2 after the prototype

- morning world digest/newspaper;
- autonomous off-screen world simulation;
- procedural quest generation;
- generalized NPC planning agents;
- larger economy;
- multiple settlements/biomes;
- complex weather/day-night;
- cloud persistence and production multiplayer frontend.

## Definition of Done

The 2026-08-30 build is accepted only when a clean player can:
1. launch the graphical game without editing code;
2. move around the start village;
3. enter the tavern;
4. speak to Oren;
5. receive and accept the firewood quest;
6. leave/return to the playable village area and collect five canonical firewood items;
7. return to Oren;
8. fail to turn in if requirements are not met;
9. successfully turn in when requirements are met;
10. receive a deterministic reward/relationship consequence exactly once;
11. receive a persistent NPC memory exactly once;
12. immediately get a changed Oren response based on the consequence;
13. fully stop and restart the game/server;
14. still observe the completed quest, relationship and memory consequence;
15. complete the same critical route using fallback dialogue when the LLM is intentionally unavailable.

Additionally:
- existing shared-world kernel tests remain green;
- new quest/persistence tests are green;
- the browser/LLM never directly mutates SQLite;
- duplicate quest completion cannot duplicate reward;
- no P2 feature is allowed to delay release.

## Verified technical acceptance — 24 Aug 2026

The feature branch has now passed an automated real-browser acceptance gate in Chromium on the same critical route defined above.

Fresh CI evidence on `feat/playable-vertical-slice`:
- Python suite: success (`39` tests at the time of this gate);
- real frontend dependency install + TypeScript/Phaser/Vite production build: success;
- real Chromium route: success.

The browser route verified:
1. clean village start;
2. physical WASD traversal to the tavern;
3. Oren quest offer through the real dialogue UI;
4. accepting `bring_5_firewood`;
5. leaving the tavern and collecting canonical firewood through interaction input;
6. an insufficient turn-in before the fifth item;
7. final deterministic completion;
8. visible reward (`15` coins), Oren trust (`10`) and changed memory-aware acknowledgement;
9. full browser reload while preserving canonical tavern location and completed quest consequences.

The acceptance job stores four browser screenshots as evidence: start village, quest offer, completed consequence, and post-reload state.

This closes the technical gameplay loop. It does **not** close production art integration: the current Phaser presentation is still a functional greybox. MASTER STYLE REFERENCE v1 remains the required source of truth for replacing those placeholders without changing the validated gameplay contract.
