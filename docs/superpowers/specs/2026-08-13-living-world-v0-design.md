# Living World v0 — Autonomous NPC Loop Design

## Product question

> Does the settlement feel meaningfully more alive when NPCs pursue simple needs and create causal state changes without a direct player command?

This is a deliberately tiny deterministic simulation, not a general AI-agent system.

## Chosen model

Use `need → goal → action → consequence` for exactly two NPCs and one shared resource chain.

Per world tick:
1. advance `world_time`;
2. apply coarse day rules;
3. evaluate Mira;
4. evaluate Kaspar;
5. persist autonomous state and append structured `world_events`.

No LLM, random planner, background worker, GOAP framework, wall-clock catch-up, or asynchronous server.

## Mira

Persistent state in `entities.state_json`:
- `wood_stock=2` initially;
- `work_cycles=0`;
- `requested_wood=false`.

Rules:
- on even ticks, if `wood_stock > 0`, Mira works: `wood_stock -= 1`, `work_cycles += 1`;
- if stock is zero and no request exists, Mira creates one `REQUEST_WOOD` state/event;
- while the request is active she waits without repeated event spam.

## Kaspar

Persistent state:
- `carrying_wood=0` initially.

When Mira has an active request:
- if not carrying wood, Kaspar goes toward `river_edge`;
- at the river he collects the existing `driftwood_1` if it is still available;
- while carrying wood he moves toward Mira;
- when co-located, he delivers: Mira `wood_stock += 1`, request clears, carrying resets.

Each NPC performs at most one autonomous action per tick.

## Shared resource and player intervention

`driftwood_1` is the same physical item for player and NPC simulation and must have tag `useful_wood`.

If the player takes it first, Kaspar cannot fabricate replacement wood and the autonomous chain remains blocked.

If the player gives `driftwood_1` to Mira through the existing `GIVE` action, that increments the same `wood_stock` and clears the same active request. No parallel quest flag is allowed.

## World events

Add append-only `world_events` separate from player `action_events`:
- `world_time`, `actor_id`, `event_type`, `target_id`, `location_id`, `data_json`, `summary`.

Allowed v0 types:
- `NPC_WORKED`;
- `NPC_REQUESTED_RESOURCE`;
- `NPC_MOVED`;
- `NPC_COLLECTED_RESOURCE`;
- `NPC_DELIVERED_RESOURCE`.

This separation prevents autonomous NPC events from contaminating the player Behavior Engine.

## Time semantics

`DayService.advance` must process every intermediate tick and accept a simulation callback. Therefore `WAIT 9` must produce the same world state and autonomous event sequence as nine `WAIT 1` actions.

The old tick-8 teleport of Mira/Kaspar conflicts with autonomous movement and is removed. Day phase labels remain.

## Player visibility

The simulation must be observable without debug UI. `LOOK` shows actual locations. TALK summaries become minimally state-aware: Mira can mention waiting for wood; Kaspar can mention carrying or failing to find it. Internal goal IDs and need scores are never shown.

The playtest report may expose compact world-event counts and the latest autonomous events.

## Persistence and determinism

All state lives in SQLite (`entities.state_json`, entity locations, `world_events`). Reopening the DB preserves the chain. No wall clock, network, random choice, or LLM participates.

## Technical success criteria

1. Clean DB + time advancement alone produces Mira work → shortage → request → Kaspar move/collect/return/deliver → Mira can work again.
2. Structured world events prove the causal chain.
3. `WAIT N` equals N single ticks.
4. Player taking `driftwood_1` changes/blocks the chain.
5. Player giving the wood to Mira satisfies the same need.
6. SQLite reopen preserves state/history.
7. Existing first-day and Behavior Engine tests remain green.
8. A deterministic demo proves the chain without TALK/GIVE commands causing it.

## Out of scope

No generic planners, utility AI, LLM agency/dialogue, autonomous Oren/animals, resource respawn, real-time offline simulation, economy, combat, hunger, procedural events, new locations/NPCs, vector memory, or multiplayer concurrency.

## Product gate

After implementation the question is: when a player notices NPC-caused changes, do they feel the world has its own business and want to interfere with or exploit it? Only positive playtest evidence justifies expanding Living World beyond v0.
