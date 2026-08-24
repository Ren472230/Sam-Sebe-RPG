# Playable Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first graphical playable vertical slice: village -> tavern -> Oren -> bring 5 firewood -> deterministic turn-in -> relationship/memory consequence -> changed dialogue -> restart persistence.

**Architecture:** Preserve the existing Python `GameService` + SQLite kernel as the only world authority. Add focused quest/dialogue services and a thin FastAPI adapter, then a Phaser 3 + TypeScript client that renders the two-scene 2.5D/greybox route and calls the Python API. LLM output is advisory and structured; deterministic Python code validates all world mutations and fallback dialogue keeps the route completable without OpenAI.

**Tech Stack:** Python 3.12+, sqlite3, pytest, FastAPI/Uvicorn, official OpenAI Python SDK Responses API, TypeScript, Vite, Phaser 3.90.0.

**Spec:** `docs/superpowers/specs/2026-08-24-playable-vertical-slice-design.md`

## Global Constraints

- Preserve the existing `GameService`, canonical SQLite state, ActionEvent evidence, idempotency, restart persistence, Clock abstraction and lazy NPC schedule catch-up.
- Only deterministic Python application logic may mutate canonical state.
- Browser and LLM must never write SQLite directly.
- The old ASCII/textmode visual direction is archived for this slice.
- P0 contains exactly two graphical scenes: village and tavern.
- P0 contains exactly one quest template: `bring_5_firewood`.
- The critical route must remain completable with `OPENAI_API_KEY` absent or the provider failing.
- Existing shared-world tests must remain green.
- Internal playable deadline: 2026-08-28. Release candidate deadline: 2026-08-30.

---

## File Structure

### Existing files to modify
- `pyproject.toml` — server/LLM runtime dependencies and test extras.
- `src/samseberpg/db.py` — additive schema/bootstrap for tavern, firewood, quests and memories only.
- `src/samseberpg/domain.py` — small typed models shared by quest/dialogue/API boundaries.
- `README.md` — local graphical build/run instructions after the route is proven.

### New Python files
- `src/samseberpg/quest.py` — deterministic quest acceptance/turn-in/read model.
- `src/samseberpg/dialogue.py` — Oren context builder, provider protocol, OpenAI adapter and deterministic fallback.
- `src/samseberpg/api.py` — FastAPI app factory and JSON HTTP adapter; no duplicated game rules.
- `src/samseberpg/server.py` — local entrypoint wiring DB, clock, services and web app.

### New Python tests
- `tests/test_vertical_slice_schema.py` — additive bootstrap/migration invariants.
- `tests/test_quest.py` — quest lifecycle, exact-once reward, relation and memory.
- `tests/test_dialogue.py` — context correctness, proposal validation and fallback behavior.
- `tests/test_api.py` — local-player session, observe/action/quest/dialogue HTTP contract.
- `tests/test_vertical_slice_acceptance.py` — full restart acceptance route.

### New frontend
- `web/package.json`, `web/tsconfig.json`, `web/vite.config.ts`, `web/index.html` — build tooling.
- `web/src/main.ts` — Phaser boot and shared UI shell.
- `web/src/api.ts` — typed HTTP client only.
- `web/src/state.ts` — local client/session state projection.
- `web/src/scenes/VillageScene.ts` — movement, hotspots, firewood pickups and tavern entrance.
- `web/src/scenes/TavernScene.ts` — Oren interaction and exit.
- `web/src/ui/DialoguePanel.ts` — dialogue/quest controls.
- `web/src/styles.css` — visual-canon-aware greybox styling that can accept production assets later.

---

### Task 1: Preserve baseline and add vertical-slice schema

**Files:**
- Modify: `src/samseberpg/db.py`
- Test: `tests/test_vertical_slice_schema.py`

**Interfaces:**
- Consumes: `GameDatabase.initialize()` and existing bootstrap conventions.
- Produces: canonical rows/tables for `tavern_interior`, `firewood_1..5`, `quests`, `npc_memories`; existing `relations` is reused.

- [ ] **Step 1: Write failing bootstrap test**

```python
def test_vertical_slice_bootstrap_is_additive_and_idempotent(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    db.initialize()
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM locations WHERE id='tavern_interior'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM entities WHERE entity_type='firewood'").fetchone()[0] >= 5
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='quests'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='npc_memories'").fetchone()[0] == 1
```

- [ ] **Step 2: Run the new test and verify it fails**

Run: `pytest -q tests/test_vertical_slice_schema.py`
Expected: FAIL because `tavern_interior`, `quests`, `npc_memories` and firewood bootstrap do not exist.

- [ ] **Step 3: Add only additive schema/bootstrap**

Add tables:

```sql
CREATE TABLE IF NOT EXISTS quests (
    id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    player_actor_id TEXT NOT NULL REFERENCES players(actor_id) ON DELETE CASCADE,
    quest_type TEXT NOT NULL,
    giver_actor_id TEXT NOT NULL REFERENCES npcs(actor_id),
    status TEXT NOT NULL CHECK (status IN ('active','completed')),
    accepted_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE (player_actor_id, quest_type)
);

CREATE TABLE IF NOT EXISTS npc_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    npc_actor_id TEXT NOT NULL REFERENCES npcs(actor_id) ON DELETE CASCADE,
    subject_actor_id TEXT REFERENCES actors(id) ON DELETE SET NULL,
    fact TEXT NOT NULL,
    importance INTEGER NOT NULL DEFAULT 50 CHECK (importance BETWEEN 0 AND 100),
    reinforcement_count INTEGER NOT NULL DEFAULT 0 CHECK (reinforcement_count >= 0),
    created_at TEXT NOT NULL,
    UNIQUE (npc_actor_id, subject_actor_id, fact)
);
```

Bootstrap `tavern_interior`, two directed edges between `village_square` and the tavern, and five portable `firewood` entities in `workshop_yard`.

- [ ] **Step 4: Run schema + existing database tests**

Run: `pytest -q tests/test_vertical_slice_schema.py tests/test_database.py tests/test_shared_world.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/samseberpg/db.py tests/test_vertical_slice_schema.py
git commit -m "feat: add vertical slice world schema"
```

---

### Task 2: Deterministic firewood quest service

**Files:**
- Create: `src/samseberpg/quest.py`
- Modify: `src/samseberpg/domain.py`
- Test: `tests/test_quest.py`

**Interfaces:**
- Produces: `QuestState`, `QuestResult`, `QuestService.get_state(player_id)`, `QuestService.accept(player_id, external_id=None)`, `QuestService.turn_in(player_id, external_id=None)`.
- `QuestService` receives `GameDatabase` and `Clock` and performs each accepted/turn-in mutation inside one `BEGIN IMMEDIATE` transaction.

- [ ] **Step 1: Write failing lifecycle tests**

Cover:
- fresh player -> `available`;
- accept -> `active` and persists after new service instance;
- turn-in with fewer than five owned `firewood` -> typed `INSUFFICIENT_FIREWOOD`, no mutation;
- turn-in with five -> `completed`, consumes exactly five firewood, adds deterministic coins, increases Oren->player trust, writes one memory and one action event;
- second turn-in -> `ALREADY_COMPLETED`, no duplicate reward/memory;
- repeated external ID -> same result without duplicate mutation.

- [ ] **Step 2: Run targeted tests and verify failure**

Run: `pytest -q tests/test_quest.py`
Expected: FAIL because `samseberpg.quest` does not exist.

- [ ] **Step 3: Add typed models**

```python
@dataclass(frozen=True, slots=True)
class QuestState:
    quest_type: str
    status: str
    required_firewood: int
    owned_firewood: int

@dataclass(frozen=True, slots=True)
class QuestResult:
    success: bool
    code: str
    summary: str
    state: QuestState
    event_id: int | None = None
    replayed: bool = False
```

- [ ] **Step 4: Implement `QuestService` minimally**

Constants:

```python
QUEST_TYPE = "bring_5_firewood"
GIVER_ID = "npc_oren"
REQUIRED_FIREWOOD = 5
REWARD_COINS = 5
TRUST_REWARD = 10
MEMORY_FACT = "The player brought Oren the requested firewood."
```

Use existing `processed_interactions` for exact-once API retries and write quest lifecycle evidence to `action_events` using action types `QUEST_ACCEPT` and `QUEST_TURN_IN` as string evidence rows. Do not route these through `GameService._resolve_action`.

- [ ] **Step 5: Run quest + kernel regression tests**

Run: `pytest -q tests/test_quest.py tests/test_shared_world.py tests/test_time_and_idempotency.py tests/test_concurrency.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/samseberpg/domain.py src/samseberpg/quest.py tests/test_quest.py
git commit -m "feat: add deterministic firewood quest"
```

---

### Task 3: Oren dialogue context, structured LLM decision and fallback

**Files:**
- Create: `src/samseberpg/dialogue.py`
- Test: `tests/test_dialogue.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `DialogueProvider.generate(context) -> DialogueDecision`, `DialogueService.talk(player_id, user_text) -> DialogueDecision`.
- `DialogueDecision` fields: `text: str`, `proposal: str | None`, `used_fallback: bool`.
- Allowlist proposal: `offer_quest:bring_5_firewood` only.

- [ ] **Step 1: Write context/fallback tests**

Use a fake provider and assert the provider context contains Oren role/activity, quest state, relation trust and persistent memory after completion. Assert provider exceptions produce deterministic Russian fallback text with `used_fallback=True` and the critical quest route remains understandable.

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest -q tests/test_dialogue.py`
Expected: FAIL because dialogue service does not exist.

- [ ] **Step 3: Implement deterministic context builder and fallback**

`DialogueService` reads state but never mutates inventory/coins/quest/relation/memory. It selects fallback copy by quest phase (`available`, `active`, `ready_to_turn_in`, `completed`).

- [ ] **Step 4: Implement OpenAI Responses provider**

Use the official SDK server-side only. Call `client.responses.create(...)` with a strict `text.format` JSON schema containing exactly:

```json
{
  "text": "string",
  "proposal": "offer_quest:bring_5_firewood | none"
}
```

Parse `response.output_text` with `json.loads`, convert `"none"` to `None`, and reject any proposal outside the allowlist. Model comes from `OPENAI_MODEL`; default to a documented GPT-5 family model. Missing `OPENAI_API_KEY` selects fallback without raising.

- [ ] **Step 5: Run dialogue tests without real API calls**

Run: `pytest -q tests/test_dialogue.py`
Expected: PASS with fake provider/failure provider only.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/samseberpg/dialogue.py tests/test_dialogue.py
git commit -m "feat: add state-aware Oren dialogue"
```

---

### Task 4: Thin local HTTP API

**Files:**
- Create: `src/samseberpg/api.py`
- Create: `src/samseberpg/server.py`
- Test: `tests/test_api.py`
- Modify: `pyproject.toml`

**Interfaces:**
- `create_app(game, quest, dialogue) -> FastAPI`.
- JSON endpoints:
  - `POST /api/session` -> stable local player ID;
  - `GET /api/state/{player_id}` -> world view + quest state + coins/relation summary;
  - `POST /api/action` -> existing `GameService.execute`;
  - `POST /api/quest/accept` -> `QuestService.accept`;
  - `POST /api/quest/turn-in` -> `QuestService.turn_in`;
  - `POST /api/dialogue` -> `DialogueService.talk`;
  - `GET /api/health` -> `{ "ok": true }`.

- [ ] **Step 1: Write FastAPI TestClient contract tests**

Assert session idempotency for synthetic identity `local-player`, state serialization, MOVE/TAKE routes, quest accept/turn-in errors and dialogue fallback with a failing provider.

- [ ] **Step 2: Run and verify failure**

Run: `pytest -q tests/test_api.py`
Expected: FAIL because API module does not exist.

- [ ] **Step 3: Implement request/response models and adapter only**

Map JSON into existing domain/services. Do not write SQL in route handlers except through read helper(s) that produce projection data.

- [ ] **Step 4: Add local server wiring**

`python -m samseberpg.server` initializes `data/world.sqlite3`, wires `SystemClock`, `GameService`, `QuestService`, `DialogueService`, and runs Uvicorn on `127.0.0.1:8000`.

- [ ] **Step 5: Run API + full Python suite**

Run: `pytest -q`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/samseberpg/api.py src/samseberpg/server.py tests/test_api.py
git commit -m "feat: expose local game HTTP adapter"
```

---

### Task 5: Phaser client foundation and typed API client

**Files:**
- Create: `web/package.json`, `web/tsconfig.json`, `web/vite.config.ts`, `web/index.html`
- Create: `web/src/main.ts`, `web/src/api.ts`, `web/src/state.ts`, `web/src/styles.css`
- Create: `web/src/scenes/VillageScene.ts`, `web/src/scenes/TavernScene.ts`

**Interfaces:**
- `GameApi.createSession()`, `GameApi.getState(playerId)`, `GameApi.action(...)`, `GameApi.acceptQuest(...)`, `GameApi.turnInQuest(...)`, `GameApi.dialogue(...)`.
- `ClientState` holds `playerId`, latest server projection and transient presentation state only.

- [ ] **Step 1: Create Vite/TypeScript/Phaser project with exact scripts**

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview"
  },
  "dependencies": { "phaser": "3.90.0" },
  "devDependencies": { "typescript": "^5", "vite": "^7" }
}
```

- [ ] **Step 2: Implement typed API wrapper**

Use `/api` relative URLs and throw a readable `ApiError` on non-2xx responses. No world mutation logic in TypeScript.

- [ ] **Step 3: Implement greybox `VillageScene`**

Use large simple shapes/placeholders aligned with visual canon colors, WASD/arrow movement, interaction prompt, five firewood hotspots and tavern entrance. Firewood interaction calls authoritative TAKE by entity ID and removes the hotspot only after server success.

- [ ] **Step 4: Implement `TavernScene`**

Render Oren hotspot and exit. Interaction opens the dialogue panel rather than embedding quest logic in the scene.

- [ ] **Step 5: Build**

Run: `cd web && npm install && npm run build`
Expected: TypeScript and Vite build succeed.

- [ ] **Step 6: Commit**

```bash
git add web
git commit -m "feat: add graphical village and tavern client"
```

---

### Task 6: Dialogue panel and complete playable quest route

**Files:**
- Create: `web/src/ui/DialoguePanel.ts`
- Modify: `web/src/main.ts`
- Modify: `web/src/scenes/VillageScene.ts`
- Modify: `web/src/scenes/TavernScene.ts`
- Modify: `web/src/styles.css`

**Interfaces:**
- `DialoguePanel.openOren(playerId)` requests dialogue and renders NPC text.
- Buttons invoke explicit authoritative API methods: accept quest or turn in quest. The LLM proposal controls which action is suggested, not whether server validation happens.

- [ ] **Step 1: Implement quest-state HUD**

Show only P0 information: firewood `n/5`, quest state and coins. No inventory screen/dashboard.

- [ ] **Step 2: Implement Oren conversation states**

`available`: talk + Accept button when proposal/fallback permits it.
`active`: reminder; if firewood <5, turn-in yields readable typed failure.
`active` with >=5: Turn in button.
`completed`: changed acknowledgement based on persistent memory/relation.

- [ ] **Step 3: Ensure API failure is visible and non-destructive**

Dialogue provider failures must still render fallback copy returned by server. Network failure renders a retry message and does not mutate local canonical assumptions.

- [ ] **Step 4: Build client again**

Run: `cd web && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "feat: connect playable firewood quest UI"
```

---

### Task 7: Restart acceptance and exploit regression

**Files:**
- Create: `tests/test_vertical_slice_acceptance.py`
- Modify earlier modules only if a failing acceptance test exposes a real defect.

**Interfaces:**
- Exercises the public service/API boundaries only; no direct state cheating except assertions.

- [ ] **Step 1: Write the full acceptance test**

Scenario:
1. initialize DB;
2. create local player;
3. move to village square/tavern logically and talk to Oren;
4. accept quest;
5. collect five bootstrapped firewood items through `GameService.execute(TAKE)`;
6. attempt duplicate/invalid turn-in paths;
7. complete once;
8. capture coins/trust/memory counts;
9. destroy/recreate DB/service objects against the same SQLite file;
10. assert quest completed, reward unchanged, memory exactly once and completed dialogue context contains the memory;
11. construct dialogue with a failing provider and assert fallback is returned.

- [ ] **Step 2: Run acceptance test and fix only observed failures**

Run: `pytest -q tests/test_vertical_slice_acceptance.py -v`
Expected: PASS.

- [ ] **Step 3: Run every Python regression**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 4: Run frontend production build**

Run: `cd web && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests src web
git commit -m "test: prove playable vertical slice restart acceptance"
```

---

### Task 8: Local launch path and release-facing documentation

**Files:**
- Modify: `README.md`
- Optionally create: `scripts/run_playable.py` only if it reduces launch to one command without hiding failures.

**Interfaces:**
- A developer/tester must be able to start the Python server and Vite client from documented commands with no code edits.

- [ ] **Step 1: Document prerequisites and exact commands**

Python:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"  # Windows
.venv/Scripts/python -m samseberpg.server
```

Frontend:

```bash
cd web
npm install
npm run dev
```

Document optional `OPENAI_API_KEY` and `OPENAI_MODEL`; explicitly state the game remains playable without them using fallback dialogue.

- [ ] **Step 2: Document acceptance route**

Write the exact 15-step route from the spec so a human can verify the build without reading code.

- [ ] **Step 3: Final verification**

Run:

```bash
pytest -q
cd web && npm run build
```

Expected: both PASS.

- [ ] **Step 4: Commit**

```bash
git add README.md scripts
git commit -m "docs: add playable vertical slice runbook"
```

---

## Plan Self-Review

- Spec coverage: existing kernel preservation, graphical client, tavern, five real firewood items, deterministic quest, exact-once reward, relation, persistent memory, state-aware dialogue, OpenAI structured output, fallback dialogue, restart persistence, P0-only scope and release route are each assigned to a task.
- No P2 system (newspaper, procedural quests, autonomous agents, cloud persistence, multiple settlements) is introduced.
- Type names are consistent across tasks: `QuestState`, `QuestResult`, `QuestService`, `DialogueDecision`, `DialogueProvider`, `DialogueService`, `create_app`.
- Browser never receives a direct database handle and LLM provider never receives a mutation callback.
