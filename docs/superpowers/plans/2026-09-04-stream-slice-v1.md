# Stream Slice v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current Living World + Living NPC + Social World vertical slice into a repeatable roughly one-hour stream build where ordinary village life, causal NPC knowledge transfer, a visiting wayfarer, and a second hospitality loop are visible and robust enough for a live audience.

**Architecture:** Keep Python/FastAPI/SQLite authoritative. Extend the existing `LivingWorldService` with one deterministic temporary visitor beat at tick 10 and one Oren hospitality request using the already-seeded `bread_loaf_1`; extend `SocialWorldService` only for wayfarer-news provenance; keep dialogue as bounded presentation over server-owned state. Add `?stream=1` as a presentation-only frontend mode, plus an isolated fixed-clock stream launcher and dedicated Playwright acceptance.

**Tech Stack:** Python 3.12, FastAPI, SQLite, OpenAI Python SDK, Phaser 3 / TypeScript / Vite, Playwright Chromium, GitHub Actions, Windows PowerShell.

**Spec:** `docs/superpowers/specs/2026-09-04-stream-slice-v1-design.md`

## Global Constraints

- Base is `feat/social-world-v1 @ 73f56bfacf88c78d2e71189099d501960199a010`; Stream Slice is stacked on top and must not merge into `main` without separate explicit user authorization.
- Keep the persistent cast Mira, Kaspar, Oren and add exactly one temporary visitor: `npc_wayfarer_1` / Talen.
- Reuse only `workshop_yard`, `village_square`, `river_edge`, and `tavern_interior` / The Wayfarer's Hearth.
- Talen arrives exactly once at world tick 10 and stays in `tavern_interior` for v1.
- Canonical external fact is exactly: `Heavy rain washed out part of the eastern road, so the next merchant caravan will be delayed.`
- Oren may learn that fact from Talen through the arrival contact; Mira and Kaspar must not receive it without another grounded route.
- Reuse `bread_loaf_1`; do not add a quest engine, crafting system, currency rule, second innkeeper, second guest-house scene, combat, seasons, or a generic rumor bus.
- Stream launcher uses isolated `data/stream-slice.sqlite3` and fixed 17:00 game clock.
- `?stream=1` changes presentation only; ordinary client behavior stays compatible.
- CI must pass without a live OpenAI API key; provider failure must fall back instead of blocking the session.
- Preserve all existing Living World, Living NPC, Social World, canonical browser, persistence, and Windows acceptance behavior.

---

## File map

- `src/samseberpg/db.py` — seed Talen as an initially absent NPC and seed runtime state for Talen/Oren without adding new tables.
- `src/samseberpg/npc_profiles.py` — Talen's bounded identity, speech style, motivations, and knowledge boundaries.
- `src/samseberpg/living_world.py` — deterministic tick-10 arrival, Oren hospitality request, and Oren bread receipt through existing `give_resource` authority.
- `src/samseberpg/social_world.py` — Talen -> Oren road-news knowledge with provenance and idempotency.
- `src/samseberpg/dialogue.py` — stream-critical fallbacks and bounded provider configuration.
- `src/samseberpg/api.py` — only if the existing state projection needs a narrow public stream projection; avoid a new mutation endpoint.
- `scripts/run_stream_slice.py` — fixed-clock isolated stream backend.
- `scripts/reset_stream_slice.py` — explicit isolated reset that can delete only `data/stream-slice.sqlite3` and WAL/SHM siblings.
- `scripts/stream_preflight.py` — deterministic backend soak / integrity check.
- `RUN_STREAM_SLICE.ps1` — Windows one-command launch wrapper.
- `web/src/api.ts` — map narrow stream state only if backend projection is additive.
- `web/src/main.ts` — detect `?stream=1`, render viewer-readable activity/event layer, hide/de-emphasize legacy clutter only in stream mode.
- `web/src/styles.css` — stream-mode presentation styles.
- `web/playwright.stream-slice.config.ts` — isolated fixed-clock browser harness.
- `web/scripts/reset-stream-slice-e2e.mjs` — isolated e2e reset.
- `web/tests-stream-slice/stream-slice.spec.ts` — complete audience-facing route.
- `web/package.json` — `test:e2e:stream-slice` command.
- `.github/workflows/prototype-web-ci.yml`, `.github/workflows/playable-candidate.yml`, `.github/workflows/windows-compatibility.yml` — add Stream Slice gates without removing existing ones.
- `docs/release/STREAM_SLICE_V1.md` — final runbook only after automated gates are green.

---

### Task 1: Seed Talen and stream runtime state

**Files:**
- Modify: `src/samseberpg/db.py`
- Modify: `src/samseberpg/npc_profiles.py`
- Create: `tests/test_stream_slice_bootstrap.py`

**Interfaces:**
- Produces actor `npc_wayfarer_1`, `npcs` row role `wayfarer`, initial `actors.location_id = NULL`, runtime state `{"arrived": false}`.
- Produces Oren runtime state `{"bread_requested": false, "bread_received": false}` while preserving existing Oren schedule/location.
- Produces `get_npc_profile("npc_wayfarer_1")` with display name `Тален`.

- [ ] **Step 1: Write the failing bootstrap/profile tests**

```python
def test_stream_bootstrap_seeds_absent_talen_and_hospitality_state(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    with db.connect() as conn:
        talen = conn.execute(
            "SELECT actors.location_id, npcs.role FROM actors JOIN npcs ON npcs.actor_id = actors.id WHERE actors.id = 'npc_wayfarer_1'"
        ).fetchone()
        assert talen is not None
        assert talen[0] is None
        assert talen[1] == "wayfarer"
        assert json.loads(conn.execute(
            "SELECT state_json FROM npc_runtime_state WHERE npc_actor_id = 'npc_wayfarer_1'"
        ).fetchone()[0]) == {"arrived": False}
        assert json.loads(conn.execute(
            "SELECT state_json FROM npc_runtime_state WHERE npc_actor_id = 'npc_oren'"
        ).fetchone()[0]) == {"bread_received": False, "bread_requested": False}


def test_talen_profile_is_bounded():
    profile = get_npc_profile("npc_wayfarer_1")
    assert profile.display_name == "Тален"
    assert profile.role == "wayfarer"
    assert "дорог" in " ".join(profile.knowledge_boundaries).lower()
```

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_stream_slice_bootstrap.py`

Expected: failures because `npc_wayfarer_1` and its profile/runtime rows do not exist.

- [ ] **Step 3: Implement minimal bootstrap**

In `db.py`, keep `_NPCS` for scheduled residents. Add Talen explicitly in `_bootstrap` so his location may be `NULL`:

```python
conn.execute(
    "INSERT OR IGNORE INTO actors (id, world_id, actor_type, name, location_id, created_at) VALUES ('npc_wayfarer_1', ?, 'npc', 'Talen', NULL, ?)",
    (DEFAULT_WORLD_ID, created_at),
)
conn.execute(
    "INSERT OR IGNORE INTO npcs (actor_id, role, current_activity) VALUES ('npc_wayfarer_1', 'wayfarer', 'travelling toward the village')"
)
```

Extend `runtime_defaults` with:

```python
("npc_oren", {"bread_requested": False, "bread_received": False}),
("npc_wayfarer_1", {"arrived": False}),
```

In `npc_profiles.py`, add `npc_wayfarer_1` with Russian display name `Тален`, tired/observant/dry personality, concise speech, motivation to rest and exchange useful road news, and knowledge boundaries limited to his own route and supplied facts.

- [ ] **Step 4: Run GREEN plus regression slice**

Run: `pytest -q tests/test_stream_slice_bootstrap.py tests/test_database.py tests/test_npc_profiles.py`

Expected: all pass.

- [ ] **Step 5: Commit**

Commit message: `feat: seed Stream Slice wayfarer`

---

### Task 2: Deterministic tick-10 arrival and Oren bread request

**Files:**
- Modify: `src/samseberpg/living_world.py`
- Create: `tests/test_stream_slice_living_world.py`

**Interfaces:**
- `LivingWorldService.advance(conn, ticks)` may return `WAYFARER_ARRIVED` and existing `NPC_REQUESTED_RESOURCE` events in the same call.
- At tick 10, Talen moves from `NULL` to `tavern_interior` exactly once.
- After Talen is present, Oren sets `bread_requested=True` exactly once and records existing `NPC_REQUESTED_RESOURCE` targeting `bread_loaf_1`.

- [ ] **Step 1: Write failing arrival/idempotency tests**

```python
def test_talen_arrives_once_at_tick_10_and_oren_requests_bread(stream_world):
    conn, service = stream_world
    first = service.advance(conn, 9)
    assert not any(e["event_type"] == "WAYFARER_ARRIVED" for e in first)
    events = service.advance(conn, 1)
    assert [e["event_type"] for e in events].count("WAYFARER_ARRIVED") == 1
    assert conn.execute("SELECT location_id FROM actors WHERE id='npc_wayfarer_1'").fetchone()[0] == "tavern_interior"
    oren = json.loads(conn.execute("SELECT state_json FROM npc_runtime_state WHERE npc_actor_id='npc_oren'").fetchone()[0])
    assert oren["bread_requested"] is True
    assert any(e["event_type"] == "NPC_REQUESTED_RESOURCE" and e["actor_id"] == "npc_oren" and e["target_id"] == "bread_loaf_1" for e in events)

    again = service.advance(conn, 5)
    all_rows = conn.execute("SELECT event_type FROM world_events WHERE event_type='WAYFARER_ARRIVED'").fetchall()
    assert len(all_rows) == 1
    assert not any(e["event_type"] == "WAYFARER_ARRIVED" for e in again)
```

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_stream_slice_living_world.py`

Expected: `WAYFARER_ARRIVED` absent and Oren runtime unchanged.

- [ ] **Step 3: Implement minimal world behavior**

Add `WAYFARER_ARRIVED` to `_ALLOWED_EVENT_TYPES`. During each tick in `advance`, call `_advance_wayfarer(conn, tick)` and then `_advance_oren_hospitality(conn, tick)`, appending non-`None` events.

`_advance_wayfarer` must require `tick >= 10`, `state.arrived == False`, then atomically update Talen's actor location/activity/runtime and call `_record_event` with summary `Talen arrived at The Wayfarer's Hearth with news from the eastern road.`

`_advance_oren_hospitality` must require Talen already at `tavern_interior`, `bread_received == False`, `bread_requested == False`, then set `bread_requested=True` and record existing `NPC_REQUESTED_RESOURCE` with `target_id='bread_loaf_1'`, `location_id='tavern_interior'`, `data={"resource_kind":"bread","for_actor_id":"npc_wayfarer_1"}`, and summary `Oren is looking for bread for the newly arrived guest.`

- [ ] **Step 4: Run GREEN and Living World regression**

Run: `pytest -q tests/test_stream_slice_living_world.py tests/test_living_world.py tests/test_living_world_acceptance.py`

Expected: all pass.

- [ ] **Step 5: Commit**

Commit message: `feat: add deterministic wayfarer arrival`

---

### Task 3: Talen -> Oren road-news provenance

**Files:**
- Modify: `src/samseberpg/social_world.py`
- Create: `tests/test_stream_slice_social_world.py`

**Interfaces:**
- Constant fact key: `wayfarer_eastern_road_delay:v1`.
- Fact text: `Heavy rain washed out part of the eastern road, so the next merchant caravan will be delayed.`
- Talen stores source kind `direct_event`, source world event = arrival event, confidence 100, shareable 1.
- Oren stores the same fact key as `npc_report`, source actor `npc_wayfarer_1`, source knowledge Talen row, confidence 95, shareable 1.
- Mira/Kaspar receive no row.

- [ ] **Step 1: Write failing causal knowledge tests**

```python
def test_wayfarer_arrival_teaches_only_talen_and_oren(stream_services):
    game, db, player_id = stream_services
    game.execute(CanonicalAction(actor_id=player_id, action_type=ActionType.WAIT, modifiers={"ticks": 10}))
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT knower_actor_id, fact_key, source_kind, source_actor_id, confidence FROM npc_knowledge WHERE fact_key='wayfarer_eastern_road_delay:v1' ORDER BY knower_actor_id"
        ).fetchall()
        assert [(r[0], r[2], r[3], r[4]) for r in rows] == [
            ("npc_oren", "npc_report", "npc_wayfarer_1", 95),
            ("npc_wayfarer_1", "direct_event", "npc_wayfarer_1", 100),
        ]
        assert conn.execute("SELECT COUNT(*) FROM npc_knowledge WHERE fact_key='wayfarer_eastern_road_delay:v1' AND knower_actor_id IN ('npc_mira','npc_kaspar')").fetchone()[0] == 0
```

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_stream_slice_social_world.py`

Expected: arrival exists after Task 2 but no road-news knowledge rows exist.

- [ ] **Step 3: Implement arrival event handling**

Extend `SocialWorldService.process_world_events` with one branch for `WAYFARER_ARRIVED`. Validate actor `npc_wayfarer_1`, target/location as expected, insert Talen direct knowledge with `ON CONFLICT(knower_actor_id, fact_key) DO NOTHING`, read its row id, then insert Oren report knowledge with source actor and source knowledge id. Keep `social_processed_events` receipt handling so replay does not duplicate knowledge.

- [ ] **Step 4: Run GREEN plus no-telepathy regressions**

Run: `pytest -q tests/test_stream_slice_social_world.py tests/test_social_world.py tests/test_social_world_propagation.py tests/test_social_world_acceptance.py`

Expected: all pass.

- [ ] **Step 5: Commit**

Commit message: `feat: propagate wayfarer news to Oren`

---

### Task 4: Bread delivery through existing TAKE/GIVE authority

**Files:**
- Modify: `src/samseberpg/living_world.py`
- Create: `tests/test_stream_slice_hospitality.py`

**Interfaces:**
- Existing `GameService` GIVE path remains authoritative and delegates to `LivingWorldService.give_resource`.
- `recipient_id='npc_oren'`, `entity_id='bread_loaf_1'` succeeds only while Oren has `bread_requested=True` and player owns the loaf.
- Success consumes the loaf from player ownership, sets Oren `bread_requested=False`, `bread_received=True`, and returns code `OK`.

- [ ] **Step 1: Write failing end-to-end service test**

```python
def test_player_can_take_square_bread_and_give_it_to_oren_after_arrival(stream_services):
    game, db, player_id = stream_services
    game.execute(CanonicalAction(actor_id=player_id, action_type=ActionType.WAIT, modifiers={"ticks": 10}))
    game.execute(CanonicalAction(actor_id=player_id, action_type=ActionType.MOVE, destination_id="village_square"))
    taken = game.execute(CanonicalAction(actor_id=player_id, action_type=ActionType.TAKE, target_id="bread_loaf_1"))
    assert taken.success
    game.execute(CanonicalAction(actor_id=player_id, action_type=ActionType.MOVE, destination_id="tavern_interior"))
    given = game.execute(CanonicalAction(actor_id=player_id, action_type=ActionType.GIVE, target_id="bread_loaf_1", recipient_id="npc_oren"))
    assert given.success and given.code == "OK"
    with db.connect() as conn:
        state = json.loads(conn.execute("SELECT state_json FROM npc_runtime_state WHERE npc_actor_id='npc_oren'").fetchone()[0])
        assert state == {"bread_received": True, "bread_requested": False}
        bread = conn.execute("SELECT location_id, owner_actor_id FROM entities WHERE id='bread_loaf_1'").fetchone()
        assert bread[0] is None and bread[1] is None
```

Also add pre-arrival / wrong-recipient tests expecting `RESOURCE_NOT_NEEDED` or existing validation codes.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_stream_slice_hospitality.py`

Expected: current `give_resource` rejects any recipient other than Mira.

- [ ] **Step 3: Implement narrow Oren bread branch**

At the top of `LivingWorldService.give_resource`, dispatch `npc_oren` + `bread_loaf_1` to `_give_bread_to_oren`; leave Mira driftwood behavior untouched. `_give_bread_to_oren` validates ownership and Oren request state, consumes the exact entity, saves Oren runtime, and returns `(True, "OK", "Gave bread_loaf_1 to Oren for the guest.")`.

- [ ] **Step 4: Run GREEN plus player intervention regressions**

Run: `pytest -q tests/test_stream_slice_hospitality.py tests/test_player_intervention.py tests/test_living_world_integration.py`

Expected: all pass.

- [ ] **Step 5: Commit**

Commit message: `feat: add Oren hospitality bread loop`

---

### Task 5: Stream-critical fallback dialogue and bounded provider calls

**Files:**
- Modify: `src/samseberpg/dialogue.py`
- Create: `tests/test_stream_slice_dialogue.py`

**Interfaces:**
- Talen fallback can state only the persisted road/caravan fact.
- Oren fallback distinguishes before bread request, bread requested, and bread received; after arrival his road-news answer must derive from `known_facts`.
- Existing Mira/Kaspar fallbacks remain valid.
- `OpenAIResponsesProvider` default client uses bounded timeout/retry values verified against current OpenAI Python SDK documentation; injected test clients remain supported.

- [ ] **Step 1: Write failing fallback tests**

```python
def test_talen_fallback_tells_only_persisted_road_news(stream_dialogue_after_arrival):
    decision = stream_dialogue_after_arrival.talk(player_id, "Что случилось в дороге?", "npc_wayfarer_1")
    assert "восточн" in decision.text.lower()
    assert "караван" in decision.text.lower()


def test_oren_fallback_requests_then_acknowledges_bread(stream_dialogue_after_arrival):
    before = service.talk(player_id, "Нужна помощь?", "npc_oren")
    assert "хлеб" in before.text.lower()
    deliver_bread()
    after = service.talk(player_id, "Хлеб подошёл?", "npc_oren")
    assert "спасибо" in after.text.lower() or "гост" in after.text.lower()
```

Add a fake provider that raises `TimeoutError` and assert `DialogueService.talk` returns `used_fallback=True` instead of raising.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_stream_slice_dialogue.py`

Expected: Talen profile may build after Task 1, but current generic fallback does not cover the stream lines.

- [ ] **Step 3: Verify SDK API before provider edit**

Use current official OpenAI Python documentation for constructor/client options. Record the verified API in the commit/PR note. Configure a default client equivalent to `OpenAI(api_key=..., timeout=8.0, max_retries=1)` only if those exact options are confirmed for the installed SDK; otherwise use the documented equivalent. Do not add a custom retry loop on top of SDK retries.

- [ ] **Step 4: Implement minimal fallback branches**

Use `context.runtime_state`, `context.known_facts`, and `context.npc_id`; do not query extra global state inside `_fallback`. Add direct branches for `npc_wayfarer_1` and Oren hospitality/news questions while preserving existing Oren quest/Mira/Kaspar behavior.

- [ ] **Step 5: Run GREEN plus dialogue regressions**

Run: `pytest -q tests/test_stream_slice_dialogue.py tests/test_living_npc_dialogue.py tests/test_living_npc_fallback.py tests/test_social_world_dialogue.py`

Expected: all pass.

- [ ] **Step 6: Commit**

Commit message: `feat: harden Stream Slice dialogue`

---

### Task 6: Viewer-readable stream state and `?stream=1`

**Files:**
- Modify: `src/samseberpg/api.py` only if existing `/api/state` lacks needed narrow data.
- Modify: `web/src/api.ts`
- Modify: `web/src/main.ts`
- Modify: `web/src/styles.css`
- Create: `web/tests/stream-mode-contract.test.ts`

**Interfaces:**
- Stream mode detection: `new URLSearchParams(window.location.search).get("stream") === "1"`.
- Presentation shows world tick/session phase, nearby NPCs, concise activities for present NPCs, and the latest 3-5 public world events already exposed by state.
- No raw trust values, event ids, JSON, source ids, or internal result codes in stream presentation.
- Non-stream DOM behavior remains compatible with existing contract/browser tests.

- [ ] **Step 1: Write failing frontend contract tests**

Create tests that import pure helper(s) extracted from `main.ts`, for example:

```ts
assert.equal(isStreamMode("?stream=1"), true);
assert.equal(isStreamMode(""), false);
assert.match(streamEventLabel({ event_type: "WAYFARER_ARRIVED", summary: "..." }), /Тален|путник/);
```

Also assert stream labels never contain `source_knowledge_id`, raw JSON braces, or `trust:`.

- [ ] **Step 2: Run RED**

Run: `cd web && node --test --experimental-strip-types tests/stream-mode-contract.test.ts`

Expected: missing helpers/stream mode.

- [ ] **Step 3: Implement presentation helpers and DOM mode**

Add exported pure helpers for stream detection/event labels; in `main.ts`, add `document.body.classList.toggle("stream-mode", streamMode)`, a compact `#stream-status` section, and reuse current state/world-pulse data. CSS de-emphasizes legacy quest/coin/trust only under `.stream-mode`.

- [ ] **Step 4: Run GREEN + full web contract/build**

Run: `cd web && npm run test:contract && npm run build`

Expected: all contract tests pass and TypeScript/Vite build exits 0.

- [ ] **Step 5: Commit**

Commit message: `feat: add Stream Slice presentation mode`

---

### Task 7: Isolated fixed-clock launcher, reset, and backend soak

**Files:**
- Create: `scripts/run_stream_slice.py`
- Create: `scripts/reset_stream_slice.py`
- Create: `scripts/stream_preflight.py`
- Create: `RUN_STREAM_SLICE.ps1`
- Create: `tests/test_stream_slice_launcher.py`

**Interfaces:**
- `STREAM_DB = Path("data/stream-slice.sqlite3")`.
- Stream app uses `FakeClock(datetime(2026, 8, 24, 17, 0, tzinfo=timezone.utc))`, `LivingWorldService()`, `SocialWorldService()`, and normal `DialogueService` provider selection rules.
- Reset is allowed to delete only `stream-slice.sqlite3`, `stream-slice.sqlite3-wal`, `stream-slice.sqlite3-shm` after resolving and confirming their parent/name.
- PowerShell launcher resets only when passed `-Reset`, then starts backend and Vite and prints `http://127.0.0.1:5173/?stream=1`.

- [ ] **Step 1: Write failing launcher safety tests**

Test fixed clock, exact DB path, and reset path guard. The reset helper should reject any path whose resolved filename is not `stream-slice.sqlite3`.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_stream_slice_launcher.py`

Expected: launcher/reset helpers absent.

- [ ] **Step 3: Implement launcher/reset/preflight**

`stream_preflight.py` creates a temporary stream database, registers a player, advances through at least tick 20, asserts one arrival, one Oren bread request, correct knowledge isolation, performs SQLite `PRAGMA integrity_check`, closes/reopens database, and exits nonzero on any invariant failure.

- [ ] **Step 4: Run GREEN**

Run: `pytest -q tests/test_stream_slice_launcher.py && python scripts/stream_preflight.py`

Expected: tests pass and preflight prints a concise PASS summary with tick/event counts and `integrity_check=ok`.

- [ ] **Step 5: Commit**

Commit message: `feat: add isolated Stream Slice launcher`

---

### Task 8: Complete backend Stream Slice acceptance

**Files:**
- Create: `tests/test_stream_slice_acceptance.py`

**Interfaces:**
- Uses only public service operations plus DB reads for assertions; no direct social-state inserts.
- Covers promise/private knowledge, autonomous Kaspar delivery, Talen arrival, Oren news, bread TAKE/GIVE, and reopen persistence in one deterministic route.

- [ ] **Step 1: Write the full acceptance route**

Test sequence:

```text
fresh DB @ fixed 17:00
register player
WAIT 5
promise Mira useful wood
MOVE square -> river
ask Kaspar; no Mira report
WAIT 4 -> tick 9 autonomous delivery
MOVE square; ask Kaspar -> Mira provenance reply
WAIT 1 -> tick 10 Talen arrival + Oren bread request
MOVE tavern; talk Talen -> eastern road/caravan fact
ask Oren -> road fact + bread need
MOVE square; TAKE bread_loaf_1
MOVE tavern; GIVE bread_loaf_1 to Oren
ask Oren -> acknowledges guest/bread
close/reopen
assert one WAYFARER_ARRIVED, one Oren bread request, Oren/Talen road knowledge only, Oren bread_received true, Kaspar promise provenance persists
```

- [ ] **Step 2: Run test**

Run: `pytest -q tests/test_stream_slice_acceptance.py`

Expected: PASS if Tasks 1-7 are correctly integrated; if it fails, treat as a real integration bug and use systematic-debugging before changing production code.

- [ ] **Step 3: Run full Python suite**

Run: `pytest -q`

Expected: zero failures.

- [ ] **Step 4: Commit**

Commit message: `test: add Stream Slice backend acceptance`

---

### Task 9: Dedicated Chromium Stream Slice acceptance

**Files:**
- Create: `scripts/run_stream_slice_e2e_server.py`
- Create: `web/playwright.stream-slice.config.ts`
- Create: `web/scripts/reset-stream-slice-e2e.mjs`
- Create: `web/tests-stream-slice/stream-slice.spec.ts`
- Modify: `web/package.json`

**Interfaces:**
- Dedicated DB: `data/e2e-stream-slice.sqlite3`.
- Dedicated outputs: `test-results-stream-slice`, `playwright-report-stream-slice`.
- Browser opens `/?stream=1` with no OpenAI key.
- Store screenshots: `stream-01-opening.png`, `stream-02-kaspar-after-contact.png`, `stream-03-wayfarer.png`, `stream-04-oren-bread.png`, `stream-05-reloaded.png`.

- [ ] **Step 1: Write browser test before production/browser harness edits**

Use the existing browser diagnostics helper and exact UI actions. Assert audience-readable text, Talen talk button at tavern after tick 10, road/caravan fallback, Oren bread request, successful bread GIVE, Oren acknowledgment, and persistence after reload.

- [ ] **Step 2: Run RED**

Run: `cd web && npm run test:e2e:stream-slice`

Expected before package/config/harness completion: command/config failure or missing stream assertions; fix harness errors until the test reaches a behavior failure, then keep production changes minimal.

- [ ] **Step 3: Add fixed-clock e2e server/config/reset/package command**

Mirror the verified Social World harness but use the stream isolated DB and `?stream=1` route.

- [ ] **Step 4: Run GREEN**

Run: `cd web && npm run test:e2e:stream-slice`

Expected: 1 Chromium route PASS, zero browser-console/page errors, screenshots created.

- [ ] **Step 5: Commit**

Commit message: `test: add Stream Slice Chromium acceptance`

---

### Task 10: CI, Windows, final evidence, and runbook

**Files:**
- Modify: `.github/workflows/prototype-web-ci.yml`
- Modify: `.github/workflows/playable-candidate.yml`
- Modify: `.github/workflows/windows-compatibility.yml`
- Create: `docs/release/STREAM_SLICE_V1.md`

**Interfaces:**
- Linux gates run existing canonical + Living NPC + Social World browser routes plus Stream Slice route.
- Windows gate runs Python suite, stream launcher safety tests/preflight, and web contract/build; browser may remain Linux if existing Windows workflow intentionally does not install Chromium.
- Browser artifacts include Stream Slice test results/report/screenshots without overwriting existing evidence.

- [ ] **Step 1: Add Stream Slice commands to CI**

Add `npm run test:e2e:stream-slice` after Social World browser acceptance in both web workflows; append stream result/report directories to artifact upload paths. Add `python scripts/stream_preflight.py` to backend/Windows verification after tests.

- [ ] **Step 2: Push exact candidate and inspect all workflow results**

Required success set:

```text
Windows Compatibility Gate
Living World Integration Gate
Prototype Web CI
Playable Candidate Gate
full Python suite
web contract suite
production build
canonical Chromium
Living NPC Chromium
Social World Chromium
Stream Slice Chromium
stream_preflight.py
```

- [ ] **Step 3: Inspect browser artifact evidence**

Download the exact candidate artifact. Verify the five Stream Slice screenshots are present and visually readable; confirm trace/video are retained on failure and no stream artifacts overwrite canonical/Living NPC/Social World evidence.

- [ ] **Step 4: Write final human stream runbook only after green evidence**

`docs/release/STREAM_SLICE_V1.md` must contain:

```text
Reset: powershell -ExecutionPolicy Bypass -File .\RUN_STREAM_SLICE.ps1 -Reset
Start: powershell -ExecutionPolicy Bypass -File .\RUN_STREAM_SLICE.ps1
URL: http://127.0.0.1:5173/?stream=1
Opening: fixed 17:00
Expected beats: Mira request around tick 5; Kaspar delivery around tick 9 if player does not intervene; Talen + Oren hospitality beat at tick 10.
Recovery: browser reload preserves DB; restart launcher without -Reset preserves session; provider failure uses fallback; -Reset starts a fresh isolated stream day.
```

Also include a 60-minute host outline as optional pacing guidance, clearly labelled as guidance rather than scripted required events.

- [ ] **Step 5: Run final verification on the exact head SHA**

Re-read the approved spec line by line against implementation and evidence. Do not claim Stream Slice v1 complete until every release-blocking requirement has fresh evidence.

- [ ] **Step 6: Update/open draft PR, do not merge**

Open or update a draft PR with base `feat/social-world-v1`, head `feat/stream-slice-v1`, exact SHA, test counts, workflow run IDs, artifact ID/digest, and known nonblocking issues. Include explicit note: `Do not merge without separate user authorization.`
