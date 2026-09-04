# Social World v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic Social World layer where NPC knowledge has provenance, private facts remain isolated until a real contact, and a canonical Kaspar→Mira delivery can create relation effects and propagate Mira’s shareable player-commitment fact to Kaspar.

**Architecture:** Extend the existing SQLite/Python authority model. `LivingWorldService` continues to generate canonical physical events; `SocialWorldService` interprets only allow-listed canonical events inside the same `GameService` transaction, writes `npc_knowledge` plus idempotency receipts, and never commits independently. `DialogueService` writes the player→Mira commitment as both durable memory and shareable knowledge, reads bounded NPC-specific knowledge into dialogue context, and uses deterministic fallback text to prove pre/post-contact knowledge without OpenAI.

**Tech Stack:** Python 3.12, SQLite, FastAPI, pytest, Phaser 3.90, TypeScript, Vite, Playwright/Chromium, GitHub Actions Windows/Linux gates.

**Spec:** `docs/superpowers/specs/2026-09-03-social-world-v1-design.md`

## Global Constraints

- Base implementation is `feat/living-npc-v1` at `35e4f9f768ba73ac1edd44dd1ee79ba46a0d5646`.
- Python remains authoritative; no second simulation or asynchronous social worker.
- Social World executes inside the caller-owned SQLite transaction and performs no `COMMIT`.
- Knowledge spreads only through allow-listed causal paths; missing knowledge remains unknown.
- LLM may phrase dialogue but may not create canonical facts, change relations, or declare physical/social events.
- v1 supports one contact path: canonical `NPC_DELIVERED_RESOURCE` from Kaspar to Mira.
- v1 propagates only `player_promised_mira_useful_wood:<player_id>` from Mira to Kaspar.
- Oren must remain uninformed by this route.
- No factions, generic rumors, deception, procedural quests, combat, Godot migration, new locations, or visual-production changes.
- Existing Living World, Living NPC, Oren quest, browser, persistence, and Windows gates must remain green.
- No merge to `main` without separate explicit user authorization.

---

### Task 1: Persistent social knowledge schema

**Files:**
- Modify: `src/samseberpg/db.py`
- Modify: `tests/test_database.py`
- Create: `tests/test_social_world_schema.py`

**Interfaces:**
- Produces table `npc_knowledge` with unique `(knower_actor_id, fact_key)`.
- Produces table `social_processed_events` keyed by `world_event_id`.
- Later tasks rely on exact column names from the approved spec.

- [ ] **Step 1: Write failing schema tests**

Add focused tests that initialize a fresh database, inspect `sqlite_master`/`PRAGMA table_info`, and prove uniqueness plus reopen persistence.

```python
def test_social_world_schema_exists(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    with db.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "npc_knowledge" in tables
        assert "social_processed_events" in tables


def test_npc_knowledge_is_unique_per_knower_and_fact(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    player_id = _register_test_player(db)
    with db.connect() as conn:
        tick = int(conn.execute(
            "SELECT tick FROM world_runtime WHERE world_id = ?",
            (DEFAULT_WORLD_ID,),
        ).fetchone()[0])
        params = (
            DEFAULT_WORLD_ID,
            "npc_mira",
            player_id,
            f"player_promised_mira_useful_wood:{player_id}",
            "The player promised Mira to bring useful wood while her workshop was blocked.",
            "player_dialogue",
            player_id,
            100,
            1,
            tick,
            "2026-09-04T00:00:00Z",
        )
        conn.execute(
            "INSERT INTO npc_knowledge "
            "(world_id, knower_actor_id, subject_actor_id, fact_key, fact_text, "
            "source_kind, source_actor_id, confidence, shareable, learned_tick, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            params,
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO npc_knowledge "
                "(world_id, knower_actor_id, subject_actor_id, fact_key, fact_text, "
                "source_kind, source_actor_id, confidence, shareable, learned_tick, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                params,
            )
```

Use an existing player-registration helper pattern from `tests/test_database.py`; do not invent a second production bootstrap path.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
python -m pytest -q tests/test_social_world_schema.py tests/test_database.py
```

Expected: failure because `npc_knowledge` / `social_processed_events` do not exist.

- [ ] **Step 3: Add schema exactly as approved**

In `_SCHEMA` add:

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
CREATE TABLE IF NOT EXISTS social_processed_events (
    world_event_id INTEGER PRIMARY KEY REFERENCES world_events(id) ON DELETE CASCADE,
    processed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_npc_knowledge_knower
ON npc_knowledge(knower_actor_id, learned_tick DESC, id DESC);
```

Place the definitions after `world_events` so the foreign key target is already declared in the schema text. Keep initialization additive and compatible with existing saves.

- [ ] **Step 4: Run focused schema tests and verify GREEN**

Run:

```bash
python -m pytest -q tests/test_social_world_schema.py tests/test_database.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/samseberpg/db.py tests/test_database.py tests/test_social_world_schema.py
git commit -m "feat: add persistent NPC knowledge schema"
```

---

### Task 2: Add canonical world-event identity to Living World results

**Files:**
- Modify: `src/samseberpg/living_world.py`
- Modify: `tests/test_living_world.py`

**Interfaces:**
- Existing `LivingWorldService.advance(conn, ticks) -> list[dict[str, object]]` remains unchanged at the method level.
- Every returned event dict additionally exposes `world_event_id: int` matching the inserted `world_events.id` row.
- `SocialWorldService` in Task 3 consumes `world_event_id` for provenance/idempotency.

- [ ] **Step 1: Write a failing additive-contract test**

Extend the existing event assertions:

```python
def test_advance_returns_persisted_world_event_id(initialized_db):
    with initialized_db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        events = LivingWorldService().advance(conn, 2)
        assert events
        event = events[0]
        assert isinstance(event["world_event_id"], int)
        row = conn.execute(
            "SELECT actor_id, event_type FROM world_events WHERE id = ?",
            (event["world_event_id"],),
        ).fetchone()
        assert row is not None
        assert row["actor_id"] == event["actor_id"]
        assert row["event_type"] == event["event_type"]
        conn.execute("ROLLBACK")
```

- [ ] **Step 2: Run the test and verify RED**

```bash
python -m pytest -q tests/test_living_world.py -k world_event_id
```

Expected: missing `world_event_id`.

- [ ] **Step 3: Return the insert identity from `_record_event`**

Use the existing insert cursor:

```python
cursor = conn.execute(
    "INSERT INTO world_events (...) VALUES (...)"
    # existing params
)
return {
    "world_event_id": int(cursor.lastrowid),
    "tick": tick,
    "actor_id": actor_id,
    "event_type": event_type,
    "target_id": target_id,
    "location_id": location_id,
    "data": data,
    "summary": summary,
}
```

Do not change persisted event semantics or event type names.

- [ ] **Step 4: Run Living World regression tests**

```bash
python -m pytest -q tests/test_living_world.py tests/test_living_world_acceptance.py
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/samseberpg/living_world.py tests/test_living_world.py
git commit -m "feat: expose canonical Living World event ids"
```

---

### Task 3: Deterministic SocialWorldService for direct delivery effects

**Files:**
- Create: `src/samseberpg/social_world.py`
- Create: `tests/test_social_world.py`

**Interfaces:**
- Produces `SocialWorldService.process_world_events(conn, events) -> list[dict[str, object]]`.
- Consumes event dictionaries containing `world_event_id`, `tick`, `actor_id`, `event_type`, `target_id`, and `data`.
- Produces deterministic social effects only for supported Kaspar→Mira useful-wood delivery events.

- [ ] **Step 1: Write RED tests for direct fact + relation + idempotency**

Test setup should persist a real `NPC_DELIVERED_RESOURCE` row, then pass the matching event dict into the new service.

```python
def test_kaspar_delivery_teaches_mira_and_improves_mira_relation(db, player_id):
    event = _persist_delivery_event(db)
    service = SocialWorldService()
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        effects = service.process_world_events(conn, [event])
        knowledge = conn.execute(
            "SELECT fact_key, source_kind, source_actor_id, confidence, shareable "
            "FROM npc_knowledge WHERE knower_actor_id = 'npc_mira'"
        ).fetchone()
        relation = conn.execute(
            "SELECT familiarity, trust FROM relations "
            "WHERE source_actor_id = 'npc_mira' AND target_actor_id = 'npc_kaspar'"
        ).fetchone()
        assert knowledge["fact_key"] == f"kaspar_delivered_useful_wood_to_mira:{event['world_event_id']}"
        assert knowledge["source_kind"] == "direct_event"
        assert knowledge["source_actor_id"] == "npc_kaspar"
        assert int(knowledge["confidence"]) == 100
        assert int(knowledge["shareable"]) == 1
        assert tuple(relation) == (5, 5)
        assert effects
        conn.execute("ROLLBACK")


def test_processing_same_delivery_twice_is_noop(db):
    event = _persist_delivery_event(db)
    service = SocialWorldService()
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        service.process_world_events(conn, [event])
        second = service.process_world_events(conn, [event])
        relation = conn.execute(
            "SELECT familiarity, trust FROM relations "
            "WHERE source_actor_id = 'npc_mira' AND target_actor_id = 'npc_kaspar'"
        ).fetchone()
        receipts = conn.execute(
            "SELECT COUNT(*) FROM social_processed_events WHERE world_event_id = ?",
            (event["world_event_id"],),
        ).fetchone()[0]
        assert second == []
        assert tuple(relation) == (5, 5)
        assert int(receipts) == 1
        conn.execute("ROLLBACK")
```

Also test unsupported/malformed events are ignored with no writes.

- [ ] **Step 2: Run RED tests**

```bash
python -m pytest -q tests/test_social_world.py
```

Expected: import/module failure.

- [ ] **Step 3: Implement the minimal deterministic service**

Use constants rather than generated text:

```python
DELIVERY_FACT_PREFIX = "kaspar_delivered_useful_wood_to_mira"
DELIVERY_FACT_TEXT = (
    "Kaspar personally delivered useful wood to Mira when her workshop was blocked."
)

class SocialWorldService:
    def process_world_events(
        self,
        conn: sqlite3.Connection,
        events: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        effects: list[dict[str, object]] = []
        for event in events:
            effect = self._process_event(conn, event)
            if effect is not None:
                effects.append(effect)
        return effects
```

`_process_event` must:

1. require an integer `world_event_id`;
2. ignore events other than `NPC_DELIVERED_RESOURCE` from `npc_kaspar` to `npc_mira` with `resource_kind == 'useful_wood'`;
3. no-op if `social_processed_events` already contains the event ID;
4. insert Mira direct knowledge with `source_world_event_id`;
5. upsert directional relation `npc_mira -> npc_kaspar` with exactly `familiarity +5`, `trust +5`, all other dimensions zero/preserved;
6. invoke `_propagate_mira_commitments(...)` from Task 4-compatible data if present, but keep that helper safe as a no-op until commitment knowledge exists;
7. insert the processing receipt only after all effects succeed;
8. use SQLite UTC time (`strftime`/existing helper convention) without owning transaction boundaries.

- [ ] **Step 4: Verify unit tests GREEN**

```bash
python -m pytest -q tests/test_social_world.py tests/test_social_world_schema.py
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/samseberpg/social_world.py tests/test_social_world.py
git commit -m "feat: add deterministic Social World event processing"
```

---

### Task 4: Seed Mira commitment knowledge and propagate it to Kaspar on real contact

**Files:**
- Modify: `src/samseberpg/dialogue.py`
- Modify: `src/samseberpg/social_world.py`
- Modify: `tests/test_living_npc_dialogue.py`
- Modify: `tests/test_living_npc_fallback.py`
- Modify: `tests/test_social_world.py`

**Interfaces:**
- Existing social action constant remains `remember_commitment:bring_useful_wood_to_mira`.
- Add helper `player_mira_commitment_fact_key(player_id: str) -> str` to keep fact-key construction centralized.
- `DialogueContext` gains `known_facts: tuple[str, ...]`.
- Mira’s commitment writes one `npc_knowledge` row with source kind `player_dialogue`, source actor player, confidence 100, shareable 1.
- On supported delivery contact, Kaspar receives the same fact key with source kind `npc_report`, source actor Mira, source knowledge ID pointing to Mira’s row, confidence 90, shareable 0.

- [ ] **Step 1: Write RED commitment-knowledge tests**

Extend the existing commitment test:

```python
def test_mira_commitment_creates_shareable_knowledge(dialogue_fixture):
    service, db, player_id = dialogue_fixture
    _move_player_to_workshop_and_request_wood(...)
    decision = service.talk(player_id, "Я принесу тебе древесину", "npc_mira")
    assert decision.social_action == REMEMBER_MIRA_WOOD_COMMITMENT
    with db.connect() as conn:
        row = conn.execute(
            "SELECT knower_actor_id, fact_key, source_kind, source_actor_id, confidence, shareable "
            "FROM npc_knowledge WHERE knower_actor_id = 'npc_mira' AND subject_actor_id = ?",
            (player_id,),
        ).fetchone()
        assert row["fact_key"] == player_mira_commitment_fact_key(player_id)
        assert row["source_kind"] == "player_dialogue"
        assert row["source_actor_id"] == player_id
        assert int(row["confidence"]) == 100
        assert int(row["shareable"]) == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM npc_knowledge WHERE knower_actor_id IN ('npc_kaspar','npc_oren') "
            "AND fact_key = ?",
            (player_mira_commitment_fact_key(player_id),),
        ).fetchone()[0] == 0
```

Also call the same commitment twice and assert one knowledge row.

- [ ] **Step 2: Write RED propagation/provenance test**

In `tests/test_social_world.py`, first seed Mira’s commitment row, then process delivery:

```python
kaspar = conn.execute(
    "SELECT source_kind, source_actor_id, source_knowledge_id, confidence, shareable, fact_text "
    "FROM npc_knowledge WHERE knower_actor_id = 'npc_kaspar' AND fact_key = ?",
    (fact_key,),
).fetchone()
assert kaspar["source_kind"] == "npc_report"
assert kaspar["source_actor_id"] == "npc_mira"
assert int(kaspar["source_knowledge_id"]) == int(mira_knowledge_id)
assert int(kaspar["confidence"]) == 90
assert int(kaspar["shareable"]) == 0
assert "Mira" in kaspar["fact_text"]
```

Add a no-contact/no-Mira-knowledge case where delivery processing does not fabricate a player commitment.

- [ ] **Step 3: Run RED tests**

```bash
python -m pytest -q tests/test_living_npc_dialogue.py tests/test_social_world.py
```

Expected: knowledge assertions fail.

- [ ] **Step 4: Implement commitment knowledge in the existing transaction**

In `dialogue.py`, keep the current `npc_memories` write and add:

```python
def player_mira_commitment_fact_key(player_id: str) -> str:
    return f"player_promised_mira_useful_wood:{player_id}"
```

During `_apply_and_persist`, after server revalidation succeeds:

```python
current_tick = int(conn.execute(
    "SELECT tick FROM world_runtime WHERE world_id = ?",
    (DEFAULT_WORLD_ID,),
).fetchone()[0])
conn.execute(
    "INSERT INTO npc_knowledge "
    "(world_id, knower_actor_id, subject_actor_id, fact_key, fact_text, source_kind, "
    "source_actor_id, confidence, shareable, learned_tick, created_at) "
    "VALUES (?, 'npc_mira', ?, ?, ?, 'player_dialogue', ?, 100, 1, ?, ?) "
    "ON CONFLICT(knower_actor_id, fact_key) DO NOTHING",
    (
        DEFAULT_WORLD_ID,
        context.player_id,
        player_mira_commitment_fact_key(context.player_id),
        MIRA_COMMITMENT_FACT,
        context.player_id,
        current_tick,
        now,
    ),
)
```

- [ ] **Step 5: Implement allow-listed Mira→Kaspar propagation**

In `SocialWorldService._propagate_mira_commitments`, select only:

```sql
SELECT id, subject_actor_id, fact_key
FROM npc_knowledge
WHERE knower_actor_id = 'npc_mira'
  AND source_kind = 'player_dialogue'
  AND shareable = 1
  AND fact_key LIKE 'player_promised_mira_useful_wood:%'
ORDER BY id
```

For each row insert Kaspar knowledge:

```python
fact_text = (
    "Mira said the player promised to bring useful wood while her workshop was blocked."
)
conn.execute(
    "INSERT INTO npc_knowledge "
    "(world_id, knower_actor_id, subject_actor_id, fact_key, fact_text, source_kind, "
    "source_actor_id, source_knowledge_id, confidence, shareable, learned_tick, created_at) "
    "VALUES (?, 'npc_kaspar', ?, ?, ?, 'npc_report', 'npc_mira', ?, 90, 0, ?, ?) "
    "ON CONFLICT(knower_actor_id, fact_key) DO NOTHING",
    (...),
)
```

Do not propagate to Oren and do not recursively propagate Kaspar’s second-hand knowledge.

- [ ] **Step 6: Verify social/dialogue unit tests GREEN**

```bash
python -m pytest -q tests/test_social_world.py tests/test_living_npc_dialogue.py tests/test_living_npc_fallback.py
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add src/samseberpg/dialogue.py src/samseberpg/social_world.py tests/test_living_npc_dialogue.py tests/test_living_npc_fallback.py tests/test_social_world.py
git commit -m "feat: propagate Mira commitment knowledge through real contact"
```

---

### Task 5: Make NPC-bounded knowledge visible to dialogue and deterministic fallback

**Files:**
- Modify: `src/samseberpg/dialogue.py`
- Modify: `tests/test_living_npc_dialogue.py`
- Modify: `tests/test_living_npc_fallback.py`

**Interfaces:**
- `DialogueContext.known_facts: tuple[str, ...]` is bounded to current `npc_id` only, maximum 8 facts.
- Prompt includes provenance-bearing compact strings.
- Kaspar fallback mentions Mira’s report only when the propagated fact exists.

- [ ] **Step 1: Write RED context-isolation tests**

```python
def test_dialogue_context_contains_only_current_npc_knowledge(...):
    # seed Mira direct knowledge and Kaspar reported knowledge
    kaspar_ctx = dialogue.build_context(player_id, "Что слышно?", "npc_kaspar")
    oren_ctx = dialogue.build_context(player_id, "Что слышно?", "npc_oren")
    assert any("Mira said" in fact for fact in kaspar_ctx.known_facts)
    assert oren_ctx.known_facts == ()
```

Assert prompt contains `known_facts:` and the source-aware fact only for Kaspar.

- [ ] **Step 2: Write RED fallback before/after test**

```python
def test_kaspar_fallback_mentions_mira_report_only_after_contact(...):
    before = dialogue.talk(player_id, "Что ты обо мне слышал?", "npc_kaspar")
    assert "Мира говорила" not in before.text
    _cause_real_delivery_contact(...)
    after = dialogue.talk(player_id, "Что ты обо мне слышал?", "npc_kaspar")
    assert "Мира говорила" in after.text
    assert "обещал" in after.text
```

- [ ] **Step 3: Run RED tests**

```bash
python -m pytest -q tests/test_living_npc_dialogue.py tests/test_living_npc_fallback.py
```

Expected: `known_facts` missing and Kaspar fallback unchanged.

- [ ] **Step 4: Load bounded known facts in `build_context`**

Query only current NPC:

```sql
SELECT fact_text, source_kind, source_actor_id, confidence
FROM npc_knowledge
WHERE knower_actor_id = ?
ORDER BY confidence DESC, learned_tick DESC, id DESC
LIMIT 8
```

Format deterministically, for example:

```python
def _format_known_fact(row) -> str:
    source = row["source_actor_id"] or row["source_kind"]
    return f"{source}: {row['fact_text']} [confidence={int(row['confidence'])}]"
```

Add to `to_prompt()`:

```python
known_facts = " | ".join(self.known_facts) or "none"
...
f"known_facts: {known_facts}",
```

Keep `knowledge_rule: You know only the supplied facts. Missing facts are unknown to you.` unchanged.

- [ ] **Step 5: Add source-aware Kaspar fallback**

Before generic Kaspar fallback response, detect the propagated fact from `context.known_facts`:

```python
if context.npc_id == "npc_kaspar" and any(
    "player promised to bring useful wood" in fact.lower()
    and "npc_mira" in fact
    for fact in context.known_facts
):
    return DialogueDecision(
        text="Каспар пожимает плечом: «Мира говорила, что ты обещал помочь ей с древесиной.»",
        used_fallback=True,
        npc_id=context.npc_id,
    )
```

Use a stable machine marker/helper if cleaner than brittle free-text matching, but do not expose knowledge from another NPC unless it is actually persisted for Kaspar.

- [ ] **Step 6: Run dialogue regression tests**

```bash
python -m pytest -q tests/test_dialogue.py tests/test_living_npc_dialogue.py tests/test_living_npc_fallback.py
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add src/samseberpg/dialogue.py tests/test_living_npc_dialogue.py tests/test_living_npc_fallback.py
git commit -m "feat: expose provenance-aware NPC knowledge in dialogue"
```

---

### Task 6: Wire Social World into the canonical WAIT transaction

**Files:**
- Modify: `src/samseberpg/game.py`
- Modify: `src/samseberpg/server.py`
- Modify: `tests/test_living_world_integration.py`
- Create: `tests/test_social_world_acceptance.py`

**Interfaces:**
- Add a protocol in `game.py`:

```python
class SocialWorldProcessor(Protocol):
    def process_world_events(
        self, conn, events: list[dict[str, object]]
    ) -> list[dict[str, object]]: ...
```

- `GameService.__init__(..., social_world: SocialWorldProcessor | None = None)` remains backwards-compatible.
- During successful WAIT: `events = living_world.advance(...)`, then `social_world.process_world_events(conn, events)` when configured, then force schedule catch-up, then record player WAIT event and commit.

- [ ] **Step 1: Write RED transaction-order integration test**

Use a spy processor:

```python
class RecordingSocialWorld:
    def __init__(self):
        self.events = None
        self.in_transaction = None

    def process_world_events(self, conn, events):
        self.events = list(events)
        self.in_transaction = conn.in_transaction
        return []


def test_wait_passes_living_world_events_to_social_world(db, clock):
    living = LivingWorldService()
    social = RecordingSocialWorld()
    game = GameService(db, clock, living_world=living, social_world=social)
    player_id = game.register_player("social-test", "Ren")
    result = game.execute(CanonicalAction(
        actor_id=player_id,
        action_type=ActionType.WAIT,
        modifiers={"ticks": 2},
    ))
    assert result.success
    assert social.in_transaction is True
    assert social.events
```

Also add a failure spy that raises and assert both `world_runtime.tick` and `world_events` roll back to their pre-WAIT values.

- [ ] **Step 2: Run RED integration tests**

```bash
python -m pytest -q tests/test_living_world_integration.py -k social_world
```

Expected: `GameService` has no `social_world` parameter.

- [ ] **Step 3: Add additive wiring**

In `game.py`:

```python
class SocialWorldProcessor(Protocol):
    def process_world_events(self, conn, events: list[dict[str, object]]) -> list[dict[str, object]]:
        ...

class GameService:
    def __init__(..., living_world=None, social_world=None):
        ...
        self.social_world = social_world
```

WAIT path:

```python
world_events = self.living_world.advance(conn, wait_ticks)
if self.social_world is not None:
    self.social_world.process_world_events(conn, world_events)
self.synchronizer.catch_up(conn, DEFAULT_WORLD_ID, now, force=True)
```

In `server.py`:

```python
from .social_world import SocialWorldService
...
game = GameService(
    db,
    clock,
    living_world=LivingWorldService(),
    social_world=SocialWorldService(),
)
```

Do not attach Social World to LOOK/MOVE/TAKE/DROP/GIVE in v1.

- [ ] **Step 4: Add full backend Social World acceptance**

`tests/test_social_world_acceptance.py` must drive real services, not direct inserts for the main scenario:

```text
fresh player
WAIT until Mira requests wood
player talks to Mira: "Я принесу тебе древесину"
assert Mira knowledge exists; Kaspar/Oren do not know
move player to Kaspar and talk before contact: no Mira-report text
WAIT enough ticks for Kaspar autonomous delivery
assert one NPC_DELIVERED_RESOURCE
assert Mira direct delivery knowledge
assert Mira->Kaspar familiarity/trust == 5/5
assert Kaspar learned the player commitment from Mira
move/talk Kaspar: fallback mentions Mira report
recreate GameDatabase/QuestService/DialogueService/GameService
assert social state and dialogue behavior persist
```

Add separate no-contact path:

```text
player promises Mira
player takes driftwood before Kaspar
player GIVE to Mira
assert Kaspar never receives promise
assert Oren never receives promise
```

- [ ] **Step 5: Run backend focused acceptance**

```bash
python -m pytest -q tests/test_social_world.py tests/test_social_world_acceptance.py tests/test_living_world_integration.py tests/test_living_npc_acceptance.py
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/samseberpg/game.py src/samseberpg/server.py tests/test_living_world_integration.py tests/test_social_world_acceptance.py
git commit -m "feat: integrate Social World into canonical WAIT"
```

---

### Task 7: Browser Social World acceptance with isolated deterministic server

**Files:**
- Create: `web/tests/social-world.spec.ts`
- Create: `web/playwright.social-world.config.ts`
- Create: `web/scripts/reset-social-world-e2e.mjs`
- Create: `scripts/run_social_world_e2e_server.py`
- Modify: `web/package.json`
- Modify: `.github/workflows/prototype-web.yml`
- Modify: `.github/workflows/playable-candidate.yml`

**Interfaces:**
- Browser test reuses existing UI/API only; no new production mutation endpoint or knowledge inspector.
- Social World e2e gets its own SQLite file and Playwright output directory.
- Fixed clock must be deterministic and use the same production app/services with only injected clock/db path changed.

- [ ] **Step 1: Write a RED browser test**

Follow the existing Living NPC e2e isolation pattern. The route must capture pre-contact, post-contact, and post-reload evidence.

Pseudo-exact Playwright flow:

```ts
test("knowledge reaches Kaspar only after real Mira contact and persists", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("[data-testid='world-tick']")).toBeVisible();

  // Advance until Mira request is visible.
  await page.getByRole("button", { name: /Подождать 5 шагов/ }).click();
  await expect(page.getByText(/Мира.*древесин|нужна.*древесин/i)).toBeVisible();

  await page.getByRole("button", { name: /Поговорить: Мира/ }).click();
  await page.locator("textarea").fill("Я принесу тебе древесину");
  await page.getByRole("button", { name: "Отправить" }).click();
  await page.getByRole("button", { name: "Закрыть" }).click();

  // Move to Kaspar before delivery and prove isolation.
  // Use existing canonical travel controls; never edit DB from browser test.
  await moveToKaspar(page);
  await page.getByRole("button", { name: /Поговорить: Каспар/ }).click();
  await page.locator("textarea").fill("Что ты обо мне слышал?");
  await page.getByRole("button", { name: "Отправить" }).click();
  await expect(page.getByText(/Мира говорила/)).toHaveCount(0);
  await page.screenshot({ path: "test-results-social-world/social-01-pre-contact.png", fullPage: true });
  await page.getByRole("button", { name: "Закрыть" }).click();

  // Let Kaspar autonomously collect/deliver.
  await waitUntilKasparDelivery(page);
  await moveToKaspar(page);
  await page.getByRole("button", { name: /Поговорить: Каспар/ }).click();
  await page.locator("textarea").fill("Что ты обо мне слышал?");
  await page.getByRole("button", { name: "Отправить" }).click();
  await expect(page.getByText(/Мира говорила.*обещал.*древесин/i)).toBeVisible();
  await page.screenshot({ path: "test-results-social-world/social-02-post-contact.png", fullPage: true });

  await page.reload();
  // Navigate/reopen Kaspar as needed after state hydration.
  await talkToKaspar(page, "Что ты обо мне слышал?");
  await expect(page.getByText(/Мира говорила.*обещал.*древесин/i)).toBeVisible();
  await page.screenshot({ path: "test-results-social-world/social-03-reloaded.png", fullPage: true });
});
```

Use actual selectors/helpers from current tests when implementing; avoid timing sleeps when a state/event selector can be awaited.

- [ ] **Step 2: Run/red-check the browser contract locally where possible**

```bash
cd web
npm run test:e2e:social-world
```

Expected before server/wiring exists: fail.

- [ ] **Step 3: Add deterministic e2e server**

Mirror the Living NPC deterministic runner, but instantiate:

```python
clock = FakeClock(datetime(2026, 9, 4, 17, 0, tzinfo=timezone.utc))
db = GameDatabase(configured_social_db_path)
db.initialize()
game = GameService(
    db,
    clock,
    living_world=LivingWorldService(),
    social_world=SocialWorldService(),
)
quest = QuestService(db, clock)
dialogue = DialogueService(db, quest, provider=None)
app = create_app(game, quest, dialogue)
```

Keep this in `scripts/run_social_world_e2e_server.py`; do not add testing switches to production server behavior.

- [ ] **Step 4: Add isolated Playwright config/reset**

Use:

- DB: `data/e2e-social-world.sqlite3`
- output: `test-results-social-world`
- report: `playwright-report-social-world`
- one worker
- webServer command pointing to `python ../scripts/run_social_world_e2e_server.py` plus the existing Vite web server strategy.

Reset script deletes only Social World test DB/artifacts.

- [ ] **Step 5: Add npm script**

`web/package.json`:

```json
"test:e2e:social-world": "node scripts/reset-social-world-e2e.mjs && playwright test -c playwright.social-world.config.ts"
```

- [ ] **Step 6: Wire CI without overwriting prior evidence**

Both Prototype Web CI and Playable Candidate should run the new route after existing contract/build/canonical/Living NPC routes.

Artifact upload must include all existing evidence plus:

```text
web/test-results-social-world/**
web/playwright-report-social-world/**
```

Never reuse `test-results` for this route.

- [ ] **Step 7: Run web gates**

```bash
cd web
npm run test:contract
npm run build
npm run test:e2e:social-world
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add web/tests/social-world.spec.ts web/playwright.social-world.config.ts web/scripts/reset-social-world-e2e.mjs scripts/run_social_world_e2e_server.py web/package.json .github/workflows/prototype-web.yml .github/workflows/playable-candidate.yml
git commit -m "test: add deterministic Social World browser acceptance"
```

---

### Task 8: Full regression, exact-SHA validation, evidence audit, PR update

**Files:**
- Modify if needed from failures discovered by gates.
- Modify: `docs/AUTONOMOUS_PLAYTEST.md` if the current document exists on the feature branch; otherwise update the existing playtest/Human Experience documentation file rather than creating a duplicate.
- Update PR #41 body after evidence exists.

**Interfaces:**
- Completion claim requires one exact feature SHA with all required gates green.
- Temporary validation PR to `main` is allowed for CI only and must be closed without merge.

- [ ] **Step 1: Run the full backend suite**

```bash
python -m pytest -q tests
```

Expected: zero failures.

- [ ] **Step 2: Run existing smoke/acceptance scripts**

Run the repository’s current canonical commands from `.github/workflows/playable-candidate.yml` and `.github/workflows/living-world-integration.yml`, including:

```text
vertical-slice backend smoke
Living World acceptance
SQLite integrity/reopen
web contract
production build
canonical Chromium
Living NPC Chromium
Social World Chromium
```

Do not substitute a narrower local test for an existing release gate.

- [ ] **Step 3: If anything fails, switch to systematic debugging**

For each failure:

1. capture exact failing assertion/log;
2. reproduce at the narrowest level;
3. identify root cause;
4. add/retain a regression test;
5. make the smallest production/test-harness fix;
6. rerun the failed gate and relevant regression suite.

Do not weaken an acceptance assertion merely to obtain green CI.

- [ ] **Step 4: Validate the exact Social World feature head against `main`**

Because PR #41 is stacked on Living NPC, create a temporary draft validation PR from `feat/social-world-v1` to `main` only after the feature branch is stable. Purpose: trigger main-only Playable Candidate/Windows/Living World gates on the exact candidate.

The validation PR body must state `CI validation only — do not merge`.

- [ ] **Step 5: Wait for and inspect all exact-SHA workflows**

Required successful checks on the same feature head:

- Windows Compatibility Gate;
- Living World Integration Gate;
- Prototype Web CI;
- Playable Candidate Gate;
- any additional mandatory repository gate triggered by the candidate.

Fetch job logs for any failure rather than assuming cause from the job title.

- [ ] **Step 6: Download and audit browser evidence artifact**

Confirm the artifact contains, at minimum:

```text
canonical JSON report
canonical Markdown report
canonical browser screenshots/report
Living NPC screenshots/report
social-01-pre-contact.png
social-02-post-contact.png
social-03-reloaded.png
Social World Playwright report
```

Visually inspect the Social World screenshots. Confirm pre-contact dialogue has no Mira-report text, post-contact does, and reload retains it.

- [ ] **Step 7: Update documentation and PR #41 with exact evidence**

PR body must include:

```text
final feature SHA
Python test count
web contract count
canonical Chromium result
Living NPC Chromium result
Social World Chromium result
Windows result
artifact ID and digest
no-telepathy result
Mira→Kaspar relation result
persistence result
known non-blocking polish only
```

Remove the stale statement that implementation has not started.

- [ ] **Step 8: Close temporary validation PR without merge**

Keep PR #41 draft/open/unmerged unless the user separately authorizes integration.

- [ ] **Step 9: Run verification-before-completion**

Use `superpowers:verification-before-completion` and re-check the final exact-SHA evidence before reporting completion.

- [ ] **Step 10: Commit final docs if changed**

```bash
git add docs/
git commit -m "docs: record Social World v1 acceptance evidence"
```

If this creates a new SHA, rerun the required final checks on that new SHA before claiming completion.
