# Audit Fix Pack A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Pilot v0.1 produce decision-quality founder-playtest evidence by repairing spoiler control, input telemetry, causal timing, Living World observability, first-day balance, consequence consistency, migration safety, and CI without expanding game scope.

**Architecture:** Keep `GameService` authoritative and deterministic. Add schema-v2 evidence/migration support, then route successful timed actions through a common completion boundary that advances Living World, captures same-location autonomous events, and writes completion-timed player events. CLI telemetry remains observational and never mutates game outcomes.

**Tech Stack:** Python 3.12+, stdlib `sqlite3`, dataclasses/JSON, pytest, GitHub Actions.

## Global Constraints

- No new locations, NPCs, items, combat/HP, economy, GOAP, LLM NPC agency, multiplayer, or Living World v1.
- `action_events.world_time` means resolved/completion tick for all new rows.
- Founder mode must not expose the action catalogue or locked abilities.
- Input telemetry is local evidence only and must not influence authoritative state.
- Player-facing autonomous feedback is same-location only; off-screen `world_events` remain hidden.
- Pilot balance: Mira flat/round stone = +1 trust/+1 coin each; useful wood = +1 trust/+0 coin; Kaspar pinecone = +1 trust/+1 coin; social lodging threshold = 2.
- NPC hit = trust -2 and hit counter; raven hit = fear +2, trust -1, deterministic flee.
- Positive `aimed_throw` utility is one-shot precision repair of `target_barrel` witnessed by Mira.
- Latest schema version is 2; migration from pre-audit schema must preserve existing state.
- PR remains unmerged unless the user explicitly requests merge.

---

### Task 1: Schema v2 and migration-safe evidence storage

**Files:**
- Modify: `src/samseberpg/db.py`
- Create: `tests/test_schema_migrations.py`

**Interfaces:**
- Produces: `LATEST_SCHEMA_VERSION = 2`
- Produces: `GameDatabase.record_input_attempt(...) -> int`
- Produces: `GameDatabase.complete_input_attempt(attempt_id: int, result_code: str) -> None`
- Produces: `GameDatabase.list_input_attempts() -> list[dict[str, Any]]`
- Produces: action-event columns `started_at_tick`, `resolved_at_tick`, `duration_ticks`

- [ ] **Step 1: Write failing migration tests**

```python
def test_fresh_database_is_schema_v2(tmp_path):
    db = GameDatabase(tmp_path / "fresh.db")
    db.initialize()
    assert db.get_schema_version() == 2
    assert "input_attempts" in db.list_tables()


def test_pre_audit_database_migrates_without_losing_state(tmp_path):
    db = create_pre_audit_database(tmp_path / "legacy.db")
    db.initialize()
    assert db.get_schema_version() == 2
    assert db.fetch_entity("mira_craftswoman")["state"]["sentinel"] == "keep"
    columns = db.table_columns("action_events")
    assert {"started_at_tick", "resolved_at_tick", "duration_ticks"} <= columns
```

- [ ] **Step 2: Run migration tests and verify RED**

Run: `pytest -q tests/test_schema_migrations.py`
Expected: failures for missing schema version / columns / telemetry table.

- [ ] **Step 3: Implement latest schema plus idempotent 1→2 migration**

Add latest columns/table to `SCHEMA`, then in `initialize()`:

```python
LATEST_SCHEMA_VERSION = 2


def initialize(self) -> None:
    with self.connect() as conn:
        conn.executescript(SCHEMA)
        self._ensure_schema_version(conn)
        self._run_migrations(conn)
```

Migration rule: databases without `schema_version` but without new action columns are treated as version 1; add missing columns with `ALTER TABLE`, backfill all old rows with `started_at_tick=world_time`, `resolved_at_tick=world_time`, `duration_ticks=0`, create `input_attempts`, then set version 2. Fresh DBs with latest columns may be marked version 2 directly.

- [ ] **Step 4: Add telemetry DB methods and tests**

```python
attempt_id = db.record_input_attempt(
    world_time=4,
    raw_text="проверю бочку",
    parser_mode="ollama",
    parser_model="qwen-local",
    recognized=True,
    canonical_action={"action_type": "LOOK"},
    parser_error=None,
    latency_ms=12.5,
)
db.complete_input_attempt(attempt_id, "OK")
assert db.list_input_attempts()[-1]["result_code"] == "OK"
```

- [ ] **Step 5: Run focused tests GREEN**

Run: `pytest -q tests/test_schema_migrations.py`
Expected: all pass.

---

### Task 2: Founder-safe input resolution and telemetry

**Files:**
- Modify: `src/samseberpg/cli.py`
- Modify: `src/samseberpg/domain.py` if a small resolution dataclass is useful
- Modify: `tests/test_cli.py`
- Modify: `tests/test_first_day_cli.py`
- Create: `tests/test_input_telemetry.py`

**Interfaces:**
- Preserve: `resolve_player_input(...) -> CanonicalAction | None` for compatibility tests.
- Produce internal `InputResolution` with `action`, `parser_mode`, `parser_model`, `parser_error`, `latency_ms`.
- CLI `--mode` choices: `founder`, `systems`; default `founder`.

- [ ] **Step 1: Add failing help-mode tests**

```python
def test_founder_help_hides_action_catalogue_and_locked_ability(...):
    text = run_cli(["--mode", "founder"], "help\nquit\n")
    assert "прицельно бросить" not in text
    assert "покормить <animal_id>" not in text
    assert "пиши" in text.lower()


def test_systems_help_lists_commands_but_hides_locked_ability(...):
    text = run_cli(["--mode", "systems"], "help\nquit\n")
    assert "покормить <animal_id>" in text
    assert "прицельно бросить" not in text
```

- [ ] **Step 2: Add failing telemetry tests for all input outcomes**

Cover deterministic success, no-parser miss, Ollama success using fake transport, and `OllamaParserError`. Assert one row per typed gameplay input and correct `parser_mode/recognized/parser_error/result_code`.

- [ ] **Step 3: Run RED tests**

Run: `pytest -q tests/test_cli.py tests/test_first_day_cli.py tests/test_input_telemetry.py`
Expected: missing mode/telemetry behavior.

- [ ] **Step 4: Implement founder/systems help and detailed resolution helper**

Use `time.perf_counter()` only for telemetry. Keep `resolve_player_input()` returning just the action; main loop uses detailed resolver and persists one attempt row before/after execution.

- [ ] **Step 5: Reveal aimed syntax only after unlock**

Systems help receives `has_aimed`; founder mode prints a one-line learned affordance only after the existing unlock notification.

- [ ] **Step 6: Run focused tests GREEN**

Run: `pytest -q tests/test_cli.py tests/test_first_day_cli.py tests/test_input_telemetry.py`

---

### Task 3: Completion-time action events and common timed finalization

**Files:**
- Modify: `src/samseberpg/game_base.py`
- Modify: `src/samseberpg/db.py`
- Create: `tests/test_action_timing.py`
- Modify: relevant existing action tests

**Interfaces:**
- Change internal `_record(...)` to accept explicit `started_at_tick`, `resolved_at_tick`, `duration_ticks` with current-tick defaults for zero-duration failures/LOOK.
- Add internal helper `_complete_timed_action(...) -> ActionResult` that advances time, captures new world events, records the action at completion, and merges observable events into result data.

- [ ] **Step 1: Write RED timing tests**

```python
def test_take_event_uses_completion_tick(db, game):
    result = game.execute(CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1"))
    event = db.list_events("player_1")[-1]
    assert event["started_at_tick"] == 0
    assert event["resolved_at_tick"] == 1
    assert event["world_time"] == 1
    assert event["duration_ticks"] == 1


def test_wait_three_uses_start_zero_resolve_three(db, game):
    game.execute(CanonicalAction("player_1", ActionType.WAIT, modifiers={"ticks": 3}))
    event = db.list_events("player_1")[-1]
    assert (event["started_at_tick"], event["resolved_at_tick"], event["duration_ticks"]) == (0, 3, 3)
```

Also assert failed action duration 0 and no world-time advance.

- [ ] **Step 2: Run timing tests RED**

Run: `pytest -q tests/test_action_timing.py`

- [ ] **Step 3: Implement `_complete_timed_action`**

Pseudo-contract:

```python
start = self._world_time(conn)
last_world_event_id = self._last_world_event_id(conn)
# immediate mutation already applied by resolver
self.day.advance(conn, ticks)
resolved = self._world_time(conn)
observed = self._observable_world_events_since(conn, last_world_event_id, player_location)
result = self._record(..., started_at_tick=start, resolved_at_tick=resolved, duration_ticks=ticks,
                      data={**data, "observed_world_events": observed})
return result
```

Refactor successful MOVE/TAKE/DROP/THROW/TALK/GIVE/FEED/WAIT to use it. LOOK/failures remain zero-duration.

- [ ] **Step 4: Move progression evaluation after timed THROW record**

Ensure the current throw is present in `action_events` before `ProgressionService.evaluate`, and unlock tick uses resolved world time.

- [ ] **Step 5: Run action/timing/progression tests GREEN**

Run: `pytest -q tests/test_action_timing.py tests/test_world_and_actions.py tests/test_throwing.py tests/test_progression.py tests/test_day.py`

---

### Task 4: Observable Living World feedback

**Files:**
- Modify: `src/samseberpg/game_base.py`
- Modify: `src/samseberpg/cli.py`
- Modify: `tests/test_living_world.py`
- Create: `tests/test_world_observability.py`

**Interfaces:**
- `ActionResult.data["observed_world_events"]` is a list of compact event dictionaries from only newly-created same-location world events.

- [ ] **Step 1: Add RED same-location/off-screen tests**

Create one test where player remains at workshop while Mira works and assert `NPC_WORKED` is returned. Create another where player is at river and Mira works off-screen and assert it is not returned.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_world_observability.py`

- [ ] **Step 3: Implement event-id boundary/filter and CLI rendering**

Render after the direct action sentence:

```text
Мира расходует древесину на работу в мастерской.
```

Do not prefix with debug IDs/event types in founder mode.

- [ ] **Step 4: Run observability + Living World tests GREEN**

Run: `pytest -q tests/test_world_observability.py tests/test_living_world.py tests/test_first_day_cli.py`

---

### Task 5: First-day balance and consequence consistency

**Files:**
- Modify: `src/samseberpg/social.py`
- Modify: `src/samseberpg/game_base.py`
- Modify: `tests/test_social.py`
- Modify: `tests/test_throwing.py`
- Create: `tests/test_consequences.py`

**Interfaces:**
- Gift rules use exact Pilot values from Global Constraints.
- `request_lodging` accepts local trust >=2.
- Successful NPC/raven hit consequences are applied inside THROW resolution before time advance.

- [ ] **Step 1: Add RED balance tests**

Assert two starter stones yield exactly 2 coins and Mira trust 2; `request_lodging` succeeds at trust 2; direct 3-coin route requires a third contribution such as Kaspar's pinecone.

- [ ] **Step 2: Add RED NPC/raven hit tests**

Use deterministic seeds that produce a hit. Assert NPC trust delta -2 plus `hit_by_player_count`, and raven fear/trust/location changes.

- [ ] **Step 3: Run RED**

Run: `pytest -q tests/test_social.py tests/test_consequences.py tests/test_throwing.py`

- [ ] **Step 4: Implement balance and minimal reactions**

Update `SocialService.GIFT_RULES`, social lodging threshold, negative-trust talk response, and THROW consequence adapters. Preserve no-HP/no-combat scope.

- [ ] **Step 5: Run focused tests GREEN**

Run: `pytest -q tests/test_social.py tests/test_consequences.py tests/test_throwing.py`

---

### Task 6: Positive aimed-throw utility

**Files:**
- Modify: `src/samseberpg/game_base.py`
- Modify: `src/samseberpg/db.py` only if bootstrap target state needs an explicit default
- Create: `tests/test_precision_utility.py`

**Interfaces:**
- One-shot `target_barrel.state.precision_fixed` boolean.
- Evidence/data key: `precision_task_completed`.

- [ ] **Step 1: Add RED tests**

Test that normal throw cannot trigger the precision task; locked aimed throw is rejected; unlocked aimed hit on barrel with Mira present sets `precision_fixed`, grants Mira trust +1 once, and a second aimed hit does not grant more trust.

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_precision_utility.py`

- [ ] **Step 3: Implement one-shot precision consequence**

Inside successful THROW hit resolution, after generic social consequences, apply the barrel condition and enrich summary/evidence.

- [ ] **Step 4: Run GREEN plus progression regression**

Run: `pytest -q tests/test_precision_utility.py tests/test_progression.py tests/test_throwing.py`

---

### Task 7: Playtest reporting and founder-readiness smoke

**Files:**
- Modify: `src/samseberpg/reporting.py`
- Modify: `scripts/playtest_report.py`
- Create: `scripts/demo_founder_readiness.py`
- Modify/Create corresponding tests

**Interfaces:**
- Report adds `input_attempts_total`, `recognized_inputs`, `unrecognized_inputs`, `parser_mode_counts`, `parser_error_counts`.
- Human report shows aggregates only.

- [ ] **Step 1: Add RED reporting tests**

Populate input attempts with deterministic/ollama/none outcomes and assert aggregates.

- [ ] **Step 2: Implement reporting aggregates**

Do not expose raw text in normal human report.

- [ ] **Step 3: Add founder-readiness smoke demo**

The demo must prove, without claiming fun:

- founder help omits locked/action-catalogue spoilers;
- an input attempt is recorded;
- same-location autonomous event becomes observable;
- two stones no longer directly buy lodging but permit social vouch;
- an obvious hostile throw creates consequence;
- precision utility can be completed after injecting/unlocking the tested ability;
- schema reports version 2.

- [ ] **Step 4: Test smoke demo**

Run: `pytest -q tests/test_reporting.py tests/test_first_day_report_render.py tests/test_founder_readiness_demo.py`

---

### Task 8: Simulation invariants, docs, and CI

**Files:**
- Create: `tests/test_invariants.py`
- Modify: `docs/superpowers/specs/2026-08-13-first-day-gameplay-design.md`
- Modify: `docs/playtests/founder-v0.1.md`
- Modify: `README.md`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- No new runtime interface.

- [ ] **Step 1: Add deterministic invariant tests**

At minimum assert:

```python
assert db.get_world_time() >= previous_time
assert not (item_is_world_visible and item_is_player_owned)
assert max(events_per_actor_per_tick.values()) <= 1
```

Parameterize WAIT equivalence over several N values and an intervention state. Assert failed actions preserve authoritative state except failure evidence.

- [ ] **Step 2: Run invariant tests**

Run: `pytest -q tests/test_invariants.py`

- [ ] **Step 3: Amend stale first-day spec**

Explicitly mark the tick-8 Mira/Kaspar teleport as superseded by Living World v0 autonomous movement.

- [ ] **Step 4: Update founder protocol/README**

Use `--mode founder` for product test and `--mode systems` for canonical diagnostics; document telemetry metrics and completion-time event semantics.

- [ ] **Step 5: Add GitHub Actions CI**

Workflow on push/PR with Python 3.12:

```yaml
- run: python -m compileall -q src scripts
- run: python -m pytest -q
```

- [ ] **Step 6: Run full fresh verification**

Run:

```text
python -m compileall -q src scripts
python -m pytest -q
PYTHONPATH=src python scripts/demo_pilot.py
PYTHONPATH=src python scripts/demo_first_day.py --db /tmp/first-day-audit.db
PYTHONPATH=src python scripts/demo_living_world.py --db /tmp/living-world-audit.db
PYTHONPATH=src python scripts/demo_founder_readiness.py --db /tmp/founder-ready.db
pip install -e . --no-build-isolation -q
sam-sebe-rpg --help
```

Expected: all commands exit 0. Tests/demos prove technical readiness only, not product validation.

- [ ] **Step 7: Verify remote snapshot and PR**

Compare Git blob SHAs for all modified production/tests/docs with the locally verified snapshot. Re-fetch PR metadata and CI status. Do not merge.
