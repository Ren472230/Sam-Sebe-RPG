# Social World v1 — Design

## Status

Approved design for the next milestone after Living NPC v1.

Base candidate: `feat/living-npc-v1` at `35e4f9f768ba73ac1edd44dd1ee79ba46a0d5646`.

Implementation branch: `feat/social-world-v1`.

No merge to `main` is part of this milestone without separate explicit user authorization.

## Product goal

Move from three individually believable NPCs to a small social world where NPCs can acquire facts from real events, remember who told them something, and let those facts affect later dialogue and relationships.

The milestone must prove one concrete invariant:

> Information only spreads through an explicit causal path. An NPC must witness an event or receive a fact during a real in-world contact before that fact can affect that NPC.

This is the next layer in the product stack:

`Living World -> Living NPC -> Social World -> Emergent Situations`.

## Current foundation to reuse

The existing candidate already provides:

- authoritative Python/FastAPI gameplay;
- SQLite persistence;
- `world_events` for deterministic autonomous events;
- `npc_memories` for durable personal memories;
- multidimensional `relations`;
- persistent `dialogue_turns`;
- Mira/Kaspar Living World resource loop;
- free-text dialogue for Mira, Kaspar and Oren;
- validated Mira commitment memory;
- deterministic fallback dialogue;
- browser MOVE / WAIT / TAKE / GIVE;
- autonomous Playwright and Windows release gates.

Social World v1 must extend these systems rather than create a second simulation or a second source of truth.

## In scope

1. Persistent NPC knowledge with provenance.
2. Direct knowledge created from selected canonical world events.
3. Shareable knowledge created from selected player dialogue commitments.
4. Deterministic information transfer during a real NPC-to-NPC contact.
5. Source tracking: the recipient knows who told them the fact.
6. One deterministic relation effect caused by a directly observed helpful action.
7. Living NPC dialogue context includes known facts separately from personal memories.
8. Offline fallback can visibly prove that propagated knowledge reached the recipient.
9. Reload persistence.
10. Idempotency: repeated processing must not duplicate knowledge or apply relation effects twice.
11. Backend, API, browser and Windows acceptance coverage.

## Explicitly out of scope

- factions;
- settlements or global reputation;
- generic rumor simulation;
- deception, lying or fact contradiction resolution;
- confidence decay;
- LLM-generated NPC-to-NPC conversations;
- autonomous LLM planning;
- procedural quests;
- combat or progression;
- Godot migration;
- new locations;
- new visual production work;
- relation changes inferred from free-form sentiment;
- broadcasting private dialogue globally;
- arbitrary propagation of every `npc_memory`.

## Architecture decision

Use a deterministic `SocialWorldService` that consumes authoritative world facts and writes social knowledge inside the same SQLite transaction as gameplay.

LLM remains a presentation/reasoning layer for dialogue only. It never creates canonical social facts, changes relationships directly, or decides that an interaction occurred.

### Rejected approach A — hidden LLM NPC conversations

Running model calls between NPCs after every meeting would make the simulation expensive, non-deterministic and hard to verify. It would also blur the boundary between authoritative world state and generated prose.

Rejected for v1.

### Rejected approach B — global shared memory

Copying relevant memories to every NPC would be simple but would recreate the exact “telepathy” problem Living NPC v1 eliminated.

Rejected.

### Selected approach C — event-driven deterministic knowledge

Canonical event/dialogue -> validated social fact -> optional contact transfer -> persistent knowledge -> later dialogue.

This keeps causality inspectable and testable.

## Data model

Add `npc_knowledge`.

Recommended schema:

```sql
CREATE TABLE IF NOT EXISTS npc_knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id TEXT NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    knower_actor_id TEXT NOT NULL REFERENCES npcs(actor_id) ON DELETE CASCADE,
    subject_actor_id TEXT REFERENCES actors(id) ON DELETE SET NULL,
    fact_key TEXT NOT NULL,
    fact_text TEXT NOT NULL,
    source_kind TEXT NOT NULL CHECK (
        source_kind IN ('direct_event', 'player_dialogue', 'npc_report')
    ),
    source_actor_id TEXT REFERENCES actors(id) ON DELETE SET NULL,
    source_world_event_id INTEGER REFERENCES world_events(id) ON DELETE SET NULL,
    source_knowledge_id INTEGER REFERENCES npc_knowledge(id) ON DELETE SET NULL,
    confidence INTEGER NOT NULL DEFAULT 100 CHECK (confidence BETWEEN 0 AND 100),
    shareable INTEGER NOT NULL DEFAULT 0 CHECK (shareable IN (0, 1)),
    learned_tick INTEGER NOT NULL CHECK (learned_tick >= 0),
    created_at TEXT NOT NULL,
    UNIQUE (knower_actor_id, fact_key)
);
```

Add index:

```sql
CREATE INDEX IF NOT EXISTS idx_npc_knowledge_knower
ON npc_knowledge(knower_actor_id, learned_tick DESC, id DESC);
```

### Why knowledge is separate from memory

`npc_memories` answers: “What personally significant experience does this NPC retain?”

`npc_knowledge` answers: “What facts does this NPC currently believe they know, and where did each fact come from?”

The distinction is required for provenance and later Social World features such as rumor chains, deception and investigations. v1 does not implement those later features.

## Knowledge identities

Facts need stable machine keys so repeated events do not create duplicate beliefs.

For v1 use a small allow-list of fact families rather than arbitrary generated text.

### Player commitment to Mira

Fact key:

`player_promised_mira_useful_wood:<player_id>`

Canonical text for Mira:

`The player promised Mira to bring useful wood while her workshop was blocked.`

Source when created:

- knower: `npc_mira`;
- subject: player;
- source kind: `player_dialogue`;
- source actor: player;
- confidence: 100;
- shareable: true;
- learned tick: current `world_runtime.tick`.

The existing durable `npc_memories` Mira commitment is retained for backwards compatibility and personal salience. The new knowledge row provides provenance and shareability.

### Kaspar helped Mira

Fact key:

`kaspar_delivered_useful_wood_to_mira:<world_event_id>`

Canonical text:

`Kaspar personally delivered useful wood to Mira when her workshop was blocked.`

Source:

- knower: `npc_mira`;
- subject: `npc_kaspar`;
- source kind: `direct_event`;
- source actor: `npc_kaspar`;
- source world event: the `NPC_DELIVERED_RESOURCE` event;
- confidence: 100;
- shareable: true;
- learned tick: event tick.

## Social event processing

`SocialWorldService` owns deterministic social interpretation of canonical events.

Suggested public surface:

```python
class SocialWorldService:
    def process_world_events(
        self,
        conn: sqlite3.Connection,
        events: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        ...
```

No commit is performed by the service.

It is called by `GameService` during WAIT after `LivingWorldService.advance(conn, ticks)` and before the outer transaction commits.

This keeps the authority flow:

`GameService transaction -> Living World -> Social World -> WorldSynchronizer -> action event -> COMMIT`.

No second clock and no asynchronous worker are introduced.

## Event contract change

`LivingWorldService._record_event` currently persists `world_events`. Social World needs the exact event identity for provenance and idempotency.

The returned event dict must therefore include the inserted `world_event_id` in addition to the existing tick/actor/type/location/target/data/summary fields.

This is an internal additive contract only.

## Direct social effect: Kaspar helps Mira

When Social World receives a real `NPC_DELIVERED_RESOURCE` event with:

- actor `npc_kaspar`;
- target `npc_mira`;
- resource kind `useful_wood`;

it performs two deterministic effects.

### 1. Mira learns the direct fact

Insert the `kaspar_delivered_useful_wood_to_mira:<event_id>` knowledge row for Mira.

### 2. Mira’s relation toward Kaspar improves

Use a deliberately small fixed effect:

- familiarity `+5`;
- trust `+5`;
- other dimensions unchanged.

The relation is directional: `npc_mira -> npc_kaspar`.

No reciprocal Kaspar relation change is inferred.

This update must be idempotent for the same world event.

## Deterministic contact propagation

The delivery event itself is a confirmed physical Mira/Kaspar contact. v1 uses that contact rather than inventing a generic background “NPCs chatted” scheduler.

After processing the direct delivery fact, Social World may transfer allow-listed shareable knowledge from Mira to Kaspar.

For v1 the only transferable player-origin fact is:

`player_promised_mira_useful_wood:<player_id>`.

If Mira knows that fact when Kaspar delivers wood, Kaspar receives a new knowledge row with:

- same `fact_key`;
- same subject player;
- canonical text suitable for Kaspar: `Mira said the player promised to bring useful wood while her workshop was blocked.`;
- source kind `npc_report`;
- source actor `npc_mira`;
- source knowledge ID = Mira’s knowledge row;
- confidence = 90;
- shareable = false for v1;
- learned tick = delivery event tick.

The lower confidence records that this is second-hand information without implementing a general trust model yet.

Because of `UNIQUE(knower_actor_id, fact_key)`, processing the same contact again cannot duplicate the belief.

## No-telepathy rule

Social World must preserve all of these cases:

1. Mira knows a private/shareable commitment immediately after the player tells her.
2. Kaspar does not know it before an explicit Mira/Kaspar contact.
3. Player `GIVE` to Mira does not automatically teach Kaspar anything if Kaspar was not part of the contact.
4. Kaspar learns the commitment only through the allow-listed delivery contact in v1.
5. Oren does not receive the fact in v1.

This is a release-blocking invariant.

## Dialogue integration

Extend `DialogueContext` with `known_facts` distinct from `memories`.

Each fact supplied to the model should include provenance in compact form, for example:

```text
known_fact: Mira said: the player promised useful wood [confidence=90]
```

Do not pass the whole `npc_knowledge` table. Query only rows where `knower_actor_id == current npc`, newest/highest confidence first, bounded to a small window such as 8 facts.

The prompt keeps the existing knowledge rule: missing facts are unknown.

### Offline fallback proof

To keep CI independent of OpenAI, Kaspar’s deterministic fallback must explicitly reflect the propagated promise when that knowledge exists, for example:

`«Мира говорила, что ты обещал помочь ей с древесиной.»`

Before propagation, the same fallback must not mention the promise.

Mira’s fallback may mention Kaspar’s help after the direct delivery fact exists, but this is optional for v1 acceptance. The critical proof is Kaspar before/after knowledge isolation.

## API and browser scope

No new public mutation endpoint is needed.

Existing APIs remain authoritative:

- `/api/action` advances the world through WAIT;
- `/api/dialogue` reads NPC-bounded context;
- `/api/state` may expose a minimal debug/read-only social projection only if required by browser acceptance.

The preferred browser acceptance verifies social knowledge through dialogue rather than exposing a player-facing knowledge inspector.

No new production UI panel is required.

## Idempotency

Knowledge insertion is naturally idempotent through the unique `(knower_actor_id, fact_key)` key.

The relation effect cannot rely on that alone because an existing knowledge row could still coexist with a repeated relation update.

Add `social_processed_events`:

```sql
CREATE TABLE IF NOT EXISTS social_processed_events (
    world_event_id INTEGER PRIMARY KEY REFERENCES world_events(id) ON DELETE CASCADE,
    processed_at TEXT NOT NULL
);
```

For an allow-listed direct social event:

1. check receipt;
2. apply knowledge/relation/propagation effects;
3. insert receipt;
4. all inside the caller transaction.

A repeated attempt for the same event returns no new effects.

## Error handling

Social World is deterministic and fail-closed.

- Unknown event types: ignore.
- Event missing required IDs/data: ignore rather than invent facts.
- Missing referenced NPC/player rows: raise only if the canonical event itself references an impossible database state; otherwise ignore unsupported social interpretation.
- Invalid confidence/shareability: prevented by schema and constants.
- Social World never partially commits because the outer GameService transaction owns rollback.

A Social World exception during a supported canonical event must roll back the entire WAIT transaction rather than leave physical and social reality inconsistent.

## Tests

### Database

- `npc_knowledge` exists after initialize;
- provenance columns and foreign keys survive reopen;
- duplicate `(knower, fact_key)` is impossible;
- `social_processed_events` enforces one processing receipt per world event.

### Dialogue commitment

- Mira commitment still writes existing `npc_memories`;
- it also writes one shareable Mira knowledge row;
- repeated commitment reinforces memory behavior but does not duplicate knowledge;
- Kaspar and Oren do not receive the fact.

### Social World unit acceptance

Given a persisted Kaspar `NPC_DELIVERED_RESOURCE` event:

- Mira gains direct delivery knowledge;
- Mira->Kaspar familiarity +5 and trust +5;
- Kaspar receives Mira’s shareable player commitment only if Mira knew it before contact;
- Kaspar provenance says source actor = Mira and source kind = `npc_report`;
- confidence is 90;
- second processing is a no-op;
- no relation values increment twice.

### No-contact isolation

- player promises Mira help;
- player takes driftwood and gives it to Mira before Kaspar delivery;
- Kaspar never receives the promise;
- Oren never receives it.

### Living World integration

Primary autonomous route:

1. fresh world/player;
2. advance until Mira requests wood;
3. player talks to Mira and promises useful wood;
4. assert Mira knows commitment and Kaspar does not;
5. player does not intervene physically;
6. advance until Kaspar independently collects and delivers driftwood;
7. assert Mira remembers/knows Kaspar helped;
8. assert Mira->Kaspar relation increased exactly once;
9. assert Kaspar learned player commitment from Mira;
10. reload/recreate services;
11. assert all social state persists.

### Dialogue acceptance

Before contact:

- Kaspar fallback does not mention Mira reporting the promise.

After delivery contact:

- Kaspar fallback mentions that Mira told him the player promised to help.

### Regression

All existing:

- Living World tests;
- Living NPC tests;
- Oren quest tests;
- API tests;
- persistence tests;
- web contract tests;
- canonical browser route;
- Living NPC browser route;
- Windows compatibility gate

must remain green.

## Browser acceptance

Extend autonomous evidence with one Social World route using a fresh deterministic SQLite database and fixed clock.

Route:

`Mira request -> player promise -> talk to Kaspar before contact -> no knowledge -> WAIT until Kaspar delivery -> talk to Kaspar after contact -> source-aware reply -> reload -> reply remains source-aware`.

Capture at least:

- pre-contact Kaspar dialogue;
- post-contact Kaspar dialogue;
- post-reload Kaspar dialogue.

No live OpenAI key is required.

## Implementation boundaries

Expected files:

- `src/samseberpg/db.py` — `npc_knowledge`, `social_processed_events`;
- new `src/samseberpg/social_world.py` — deterministic processing;
- `src/samseberpg/dialogue.py` — seed commitment knowledge + bounded known facts + fallback proof;
- `src/samseberpg/living_world.py` — additive event ID in returned event dict;
- `src/samseberpg/game.py` — invoke Social World in the existing WAIT transaction;
- `src/samseberpg/server.py` / construction wiring as needed;
- focused Python tests;
- Playwright Social World acceptance and CI wiring.

Avoid unrelated refactors.

## Success criterion

Social World v1 is complete only when the system proves all of the following on one exact candidate SHA:

1. a player-origin fact is private to Mira before contact;
2. Kaspar independently acts in the Living World;
3. a real Kaspar/Mira contact creates a direct social consequence;
4. Mira’s directional relation toward Kaspar changes exactly once;
5. Mira can transmit the allow-listed player fact to Kaspar;
6. Kaspar retains provenance that Mira was the source;
7. Kaspar dialogue changes only after the causal information path exists;
8. reload preserves the result;
9. Oren remains uninformed;
10. all previous Living World, Living NPC, browser and Windows gates remain green.

This milestone deliberately stops there. Broader rumor propagation, contradictory beliefs, reputation and emergent quest generation belong to later milestones.