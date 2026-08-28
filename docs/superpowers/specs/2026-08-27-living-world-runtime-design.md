# Living World Runtime Integration — Design

## Goal

Add the first deterministic Living World backend slice on top of the current playable vertical-slice backend without changing the existing frontend, visual assets, Oren quest loop, economy rewards, dialogue contract, or canonical HTTP API behavior.

The product outcome is a small but real causal loop:

`Mira works -> wood stock is depleted -> Mira requests wood -> Kaspar temporarily leaves his schedule -> Kaspar collects the real shared driftwood entity -> Kaspar returns -> Kaspar delivers -> both NPCs return to normal schedule control`.

This is intentionally not a generic agent framework.

## Base and isolation

Implementation branch: `dev/living-world-runtime`.

Exact base: `main` at `ecdd796e5a425d77f7911b5293588ed496b4f619`.

Do not modify:

- `web/**`;
- production visual assets or manifest files;
- PR #14 / `dev/production-visual-integration`;
- Oren quest semantics;
- canonical 5-firewood turn-in;
- coins or Oren trust rewards;
- dialogue endpoint contract;
- existing location IDs.

All database changes are additive and must preserve existing saves.

## Existing architecture constraint

The current backend already has `WorldSynchronizer`, which resolves NPC locations and activities from wall-clock schedules. The historical Living World v0 code moved Mira and Kaspar directly by discrete simulation tick.

Those two mechanisms must not write NPC positions independently without arbitration.

The chosen rule is:

> schedule is the default controller; an explicit autonomous goal may temporarily override schedule for that NPC; when the goal ends, schedule immediately becomes authoritative again.

There remains only one canonical physical location for an NPC: `actors.location_id`.

No parallel simulation-position field is allowed.

## Persistent runtime model

Add three additive tables.

### `world_runtime`

One row per world:

- `world_id TEXT PRIMARY KEY`;
- `tick INTEGER NOT NULL DEFAULT 0 CHECK (tick >= 0)`.

The tick is deterministic simulation time used only by the Living World slice. It does not replace wall-clock scheduling.

### `npc_runtime_state`

One row per participating NPC:

- `npc_actor_id TEXT PRIMARY KEY REFERENCES npcs(actor_id) ON DELETE CASCADE`;
- `override_active INTEGER NOT NULL DEFAULT 0 CHECK (override_active IN (0, 1))`;
- `state_json TEXT NOT NULL DEFAULT '{}'`;
- `updated_tick INTEGER NOT NULL DEFAULT 0 CHECK (updated_tick >= 0)`.

Bootstrap state:

- `npc_mira`: `{"wood_stock":2,"work_cycles":0,"requested_wood":false}`;
- `npc_kaspar`: `{"carrying_wood":0,"goal":null}`.

`override_active=1` means wall-clock schedule must not move that NPC until the autonomous goal is resolved.

### `world_events`

Append-only autonomous events, separate from player `action_events`:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`;
- `world_id TEXT NOT NULL REFERENCES worlds(id) ON DELETE CASCADE`;
- `tick INTEGER NOT NULL`;
- `actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE`;
- `event_type TEXT NOT NULL`;
- `target_id TEXT`;
- `location_id TEXT REFERENCES locations(id)`;
- `data_json TEXT NOT NULL DEFAULT '{}'`;
- `summary TEXT NOT NULL`.

Allowed first-slice event types:

- `NPC_WORKED`;
- `NPC_REQUESTED_RESOURCE`;
- `NPC_MOVED`;
- `NPC_COLLECTED_RESOURCE`;
- `NPC_DELIVERED_RESOURCE`.

Autonomous events must never be written into `action_events`.

## Shared resource

Bootstrap one real portable entity:

- id: `driftwood_1`;
- name: `Driftwood`;
- entity type: `material`;
- initial location: `river_edge`;
- portable: `1`;
- `state_json`: `{"resource_kind":"useful_wood"}`.

Kaspar may collect only this existing entity. He must never fabricate replacement wood.

Collection sets both `location_id` and `owner_actor_id` to `NULL` and records `carrying_wood=1` in Kaspar runtime state. The item remains consumed from the physical world until a later feature explicitly introduces respawn or inventory ownership for NPCs.

## LivingWorldService

Create `src/samseberpg/living_world.py` with a focused `LivingWorldService`.

Primary interface:

```python
class LivingWorldService:
    def advance(self, conn: sqlite3.Connection, ticks: int) -> list[dict[str, object]]:
        ...
```

Rules:

- `ticks` must be between `1` and `60` inclusive;
- process every intermediate tick individually;
- increment and persist `world_runtime.tick` before evaluating that tick;
- evaluate Mira first, then Kaspar;
- each NPC performs at most one autonomous action per tick;
- all changes occur inside the caller's existing transaction.

### Mira behavior

- On even ticks, while `wood_stock > 0`, Mira works: decrement stock and increment work cycles; emit `NPC_WORKED`.
- When `wood_stock == 0` and no request exists, set `requested_wood=true`, set Mira `override_active=1`, anchor her canonical location to `workshop_yard`, and emit exactly one `NPC_REQUESTED_RESOURCE`.
- While the request remains active, no repeated request events are emitted.

### Kaspar behavior

When Mira has an active request:

1. Set Kaspar `override_active=1` and goal `collect_wood` or `deliver_wood`.
2. If Kaspar is not carrying wood and is not at `river_edge`, move one graph hop toward `river_edge`; emit `NPC_MOVED`.
3. If Kaspar is at `river_edge` and `driftwood_1` is physically there and unowned, collect it; emit `NPC_COLLECTED_RESOURCE`.
4. If carrying wood and not co-located with Mira, move one graph hop toward Mira; emit `NPC_MOVED`.
5. If carrying wood and co-located with Mira, deliver it: Mira `wood_stock += 1`, Mira request clears, Kaspar carrying clears, both overrides clear, Kaspar goal clears; emit `NPC_DELIVERED_RESOURCE`.

If `driftwood_1` is absent, Kaspar stays blocked without inventing a resource or emitting duplicate collection events.

The first slice uses only existing graph edges; no hard-coded teleporting.

## Schedule arbitration

`WorldSynchronizer` remains the schedule authority for all NPCs without an active override.

Its schedule application must skip an NPC when:

```sql
EXISTS (
    SELECT 1
    FROM npc_runtime_state
    WHERE npc_actor_id = ? AND override_active = 1
)
```

`catch_up` should support a forced schedule pass for already-synchronized wall-clock timestamps. The normal path retains the existing idempotent timestamp behavior.

After `WAIT` finishes processing its requested ticks, `GameService` performs a forced schedule pass. NPCs whose autonomous overrides are still active remain untouched; NPCs whose goals just completed immediately return to the current wall-clock schedule.

This makes the schedule/autonomy precedence explicit and prevents two sources of truth.

## WAIT action

Extend `ActionType` additively with `WAIT`.

Extend `CanonicalAction` with:

```python
modifiers: dict[str, int] | None = None
```

`WAIT` accepts `ticks` from modifiers, defaulting to `1`.

Validation:

- integer only;
- minimum `1`;
- maximum `60`;
- invalid values return a deterministic action failure and do not mutate simulation state.

On success, `GameService.execute` calls `LivingWorldService.advance` within the same transaction, then runs a forced schedule pass, records one normal player `WAIT` action event, and returns success.

`WAIT 9` must produce the same autonomous state and world-event sequence as nine separate `WAIT 1` actions from the same initial database and clock.

No frontend changes are required in this slice. The action exists first as backend capability and test surface.

## API compatibility

The existing `/api/action` request shape remains compatible. Add optional:

```json
{"modifiers":{"ticks":9}}
```

Existing clients that never send `modifiers` continue to work unchanged.

No existing response fields are removed or renamed.

No new endpoint is required for this slice.

## Bootstrap and legacy saves

`GameDatabase.initialize()` must create the new tables and insert missing runtime rows/resources using additive `INSERT OR IGNORE` semantics.

Reopening an existing database must:

- preserve all player, quest, relation, inventory, memory, and event data;
- preserve existing runtime state if the new slice has already run;
- add only missing default runtime rows;
- never reset `world_runtime.tick`;
- never respawn `driftwood_1` after it has been consumed on an already-migrated save.

To distinguish first migration from later reopen, resource bootstrap follows the same persistent bootstrap lifecycle as existing canonical entities: create only if the entity ID has never existed in that database.

## Tests and release gates

New focused tests must cover:

1. additive schema/bootstrap on a clean DB;
2. additive migration on an existing P0 save;
3. Mira works twice, then produces exactly one resource request;
4. Kaspar collects the real `driftwood_1`, moves through existing edges, and delivers;
5. `WAIT 9` equals nine `WAIT 1` calls;
6. missing driftwood blocks collection and delivery without fabrication;
7. SQLite close/reopen mid-chain preserves state and continues correctly;
8. active autonomous override prevents wall-clock schedule relocation;
9. completed autonomous goal clears override and forced schedule pass restores scheduled location/activity;
10. invalid WAIT tick counts do not mutate runtime state;
11. player `action_events` contain one WAIT entry while autonomous events remain exclusively in `world_events`;
12. existing Python backend tests and vertical-slice acceptance tests remain green.

The final gate before the branch is considered mergeable is the full current Python suite plus the existing vertical-slice smoke path. If browser/client tests are available, they are regression-only: no frontend code is expected to change.

## Explicit non-goals

This slice does not add:

- generic GOAP/utility planning;
- LLM-controlled NPC agency;
- autonomous Oren;
- autonomous animals;
- resource respawn;
- economy simulation;
- crafting;
- combat;
- factions;
- offline wall-clock catch-up for Living World ticks;
- background workers;
- multiplayer simulation scheduling;
- player `GIVE` intervention;
- new dialogue behavior;
- new frontend UI;
- new visual assets.

Player intervention with the same physical resource is the intended next small backend slice after this runtime foundation is proven green.

## Success criterion

The slice is successful when the current playable vertical slice behaves exactly as before, while a deterministic backend WAIT sequence proves that Mira and Kaspar can create and resolve one persistent, observable, causal need-resource loop without LLM control and without fighting the existing schedule system.