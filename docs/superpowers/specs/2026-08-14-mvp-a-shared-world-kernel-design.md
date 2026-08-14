# MVP-A Shared World Kernel — Design Specification

## Product hypothesis

MVP-A tests whether a tiny shared persistent world already feels meaningfully alive when several real players can alter one canonical village, leave durable traces for each other, and return later to find that time and NPC schedules have continued to matter.

The slice succeeds when one player's action creates a persistent world change another player can independently observe, the change survives restart, and an offline interval changes at least one NPC's state without an always-running simulation loop.

## Scope

MVP-A is multiplayer-first for 2–5 players in one shared village.

Included:
- 1 world with 3 locations;
- 3 NPCs with real-time schedules;
- player identities mapped from Discord user IDs;
- 10–15 simple entities/items;
- canonical SQLite state;
- lazy real-time catch-up through a replaceable Clock;
- LOOK, MOVE, TAKE, DROP;
- append-only action events for successes and gameplay failures;
- atomic state mutation + event persistence;
- idempotency keyed by external interaction ID;
- Discord-independent simulation/service boundary.

Excluded now:
- combat/PvP, crime/stealth/locks;
- organizations, businesses, crafting, magic;
- autonomous LLM agents or AI-generated mechanics;
- vector DB/RAG;
- continuous per-second simulation;
- Discord Activity/web frontend;
- PostgreSQL, Redis, brokers, microservices;
- large world generation, multiple regions, dynamic lighting.

## Core invariants

1. SQLite is the canonical source of world truth.
2. Only deterministic application/simulation code mutates canonical state.
3. Discord, parsers, renderers and future LLM components are adapters and cannot write state directly.
4. Every gameplay action is processed in one write transaction.
5. State mutation and its ActionEvent commit atomically.
6. The same external interaction ID cannot mutate the world twice.
7. World time comes from a Clock abstraction; players cannot fast-forward the shared world.
8. Offline simulation is lazy: catch-up runs when the world is touched.
9. Invalid gameplay attempts return typed ActionResult failures rather than application exceptions.
10. Programmer/data-integrity errors fail fast as exceptions.

## Architecture

Single Python process + single SQLite database:

```text
Discord / tests / debug CLI
        |
        v
     adapters
        |
        v
 CanonicalAction
        |
        v
   GameService -----> WorldSynchronizer + Clock
        |
        +-----------> deterministic rules
        |
        v
 SQLite transaction
   |       |       |
 state   event   idempotency
        |
        v
   ActionResult
```

The simulation package has no dependency on Discord or any LLM SDK.

Primary boundary:

`GameService.execute(action: CanonicalAction, external_id: str | None = None) -> ActionResult`

Read boundary:

`GameService.observe(player_id: str) -> WorldView`

Both paths synchronize deterministic due changes up to `Clock.now()` before producing their result.

## Canonical actions

Initial ActionType values:
- LOOK;
- MOVE;
- TAKE;
- DROP.

CanonicalAction contains:
- actor_id;
- action_type;
- target_id optional;
- destination_id optional;
- source_text optional and non-authoritative.

## SQLite schema

### worlds
`id`, `name`, `timezone`, `created_at`, `last_simulated_at`.
Canonical timestamps are UTC ISO-8601 strings.

### locations
`id`, `world_id`, `name`, `description`, `sort_order`.
Initial IDs: `workshop_yard`, `village_square`, `river_edge`.

### location_edges
Explicit directed adjacency between locations.

### actors
Common identity for players and NPCs: `id`, `world_id`, `actor_type`, `name`, `location_id`, `created_at`.

### players
`actor_id`, unique `discord_user_id`, `joined_at`, `coins`.
Registration is idempotent: one Discord user maps to one player actor.

### npcs
`actor_id`, `role`, `current_activity`.
Initial NPCs: Mira the craftswoman, Oren the innkeeper, Kaspar the forager.

### npc_schedule
`id`, `npc_actor_id`, `start_minute_local`, `end_minute_local`, `location_id`, `activity`, `priority`.
The kernel uses deterministic daily schedule windows; weekday-specific rules are deferred.

### entities
`id`, `world_id`, `name`, `entity_type`, nullable `location_id`, nullable `owner_actor_id`, `portable`, `state_json`, `created_at`.
Invariant: an entity cannot simultaneously have a location and an owner.

### relations
Reserved now to avoid a later identity/schema break: source/target actor IDs plus familiarity, trust, affinity, fear, conflict, romance, updated_at. The kernel does not yet change them through gameplay.

### action_events
Append-only evidence: `id`, `world_id`, nullable `external_id`, `occurred_at`, `actor_id`, `action_type`, nullable `target_id`, nullable `location_id`, `success`, `result_code`, `summary`, `evidence_json`.

### processed_interactions
`external_id` primary key, `world_id`, `actor_id`, `action_event_id`, `result_json`, `processed_at`.
Duplicate external IDs return the stored result and do not rerun the action.

## SQLite behavior

Connections enable foreign keys, WAL where supported for persisted files, and a short busy timeout. Gameplay write paths use `BEGIN IMMEDIATE` so two concurrent actions cannot both validate against stale pre-mutation state and then commit conflicting results.

For 2–5 players in one process, deliberate write serialization is preferred over larger infrastructure.

## World clock and offline catch-up

Clock protocol:

```python
class Clock(Protocol):
    def now(self) -> datetime: ...
```

Implementations:
- `SystemClock` for production;
- `FakeClock` for tests/scenarios.

`WorldSynchronizer.catch_up(conn, world_id, now)` reads `last_simulated_at`, resolves every NPC's schedule at `now`, applies only necessary location/activity changes, records meaningful world changes where needed, then advances `last_simulated_at`.

It does not replay every missed minute. It computes the state that should be true now. This tests offline liveness without building a tick engine.

## Gameplay rules

### LOOK
Returns the current location, visible actors, and location entities. It records an ActionEvent but does not mutate world objects.

### MOVE
Requires destination adjacency from the current location. Success changes actor location. Failure: `INVALID_DESTINATION`.

### TAKE
Requires an existing portable entity at the actor's current location with no owner. Success clears location_id and sets owner_actor_id. Failures: `TARGET_NOT_FOUND`, `TARGET_NOT_PRESENT`, `NOT_PORTABLE`, `ALREADY_OWNED`.

### DROP
Requires the actor to own the entity. Success clears owner and places it at the actor's location. Failure: `ITEM_NOT_OWNED`.

## First multiplayer proof

1. Player A and B register in the same world.
2. Both initially observe `stone_flat_1` in `workshop_yard`.
3. Player A TAKEs it.
4. Player B observes and no longer sees it on the ground.
5. Reopen the database: Player A still owns it.
6. Advance FakeClock into another schedule window.
7. Player B observes and sees Mira at her scheduled new location.

This proves shared state, cross-player consequence, restart persistence and offline catch-up before free-form language or richer mechanics.

## Discord boundary

The next adapter maps Discord guild to the MVP world, Discord user to player registration/lookup, `/look` to observation, and `/act` initially to a small deterministic parser. Interaction IDs are passed as `external_id`. No bot token is committed; runtime configuration uses environment variables.

## Error handling

Gameplay failures are ActionResult values and are recorded as evidence. Database integrity failures, invalid bootstrap data, unsupported schema versions and broken invariants raise exceptions.

A duplicate external interaction returns the original ActionResult with `replayed=True` and creates no second event or mutation.

## Testing strategy

Use temporary real SQLite files rather than persistence mocks.

Required tests:
- schema and foreign keys initialize correctly;
- bootstrap is idempotent;
- two Discord users register as two actors in one world;
- both observe the same initial entity;
- TAKE atomically transfers ownership and appends one event;
- another player immediately stops seeing the taken entity;
- DROP returns it to the actor's current location;
- invalid MOVE/TAKE/DROP produce typed failures and failure events;
- duplicate external_id replays the original result without another event/mutation;
- restart preserves ownership and event history;
- FakeClock changes NPC schedule state through lazy catch-up;
- core code does not call datetime.now directly;
- concurrent TAKE attempts for one entity yield exactly one success.

A scripted demo exercises the same cross-player scenario from a clean database.

## Technology decisions

- Python 3.12+;
- standard library first;
- pytest as the only initial development dependency;
- direct sqlite3, no ORM;
- dataclasses/enums for domain models;
- one process;
- no Docker requirement;
- no paid service requirement;
- source layout under `src/samseberpg`.

Discord library selection is deferred until the kernel is green so the adapter remains replaceable.

## Definition of Done

The Shared World Kernel is complete when a clean DB bootstraps the village, at least two players can register, LOOK/MOVE/TAKE/DROP work through GameService, one player's TAKE changes another player's view, restart preserves the result, FakeClock changes NPC schedule state through observation, every non-duplicate action attempt produces exactly one ActionEvent, duplicate external IDs cannot duplicate mutations, a concurrent TAKE conflict yields exactly one success, and all tests pass without Discord or LLM dependencies.

## Deferred next slices

After this kernel is verified:
1. Discord adapter with `/look`, `/me`, `/act`;
2. GIVE, THROW, USE, BUY with deterministic consequences;
3. relation mutation and one visible cross-player world consequence;
4. structured natural-language intent parsing behind a provider interface;
5. one Behavior → Achievement → Ability branch;
6. morning world digest once enough events exist to summarize meaningfully.
