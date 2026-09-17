# Living NPC v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Oren-only quest dialogue prototype into a grounded three-NPC Living NPC vertical slice where Oren, Mira and Kaspar can be spoken to in free text, remember recent conversation, expose only bounded knowledge, and connect dialogue to the existing Mira/Kaspar autonomous wood situation without allowing the LLM to mutate physical world state directly.

**Architecture:** Keep Python/FastAPI + SQLite + `GameService`/`LivingWorldService` authoritative. `DialogueService` builds an NPC-scoped context from static profile, self/runtime state, co-located perception, relation vector, durable `npc_memories`, recent same-NPC dialogue turns and NPC-specific state; the provider returns text plus allow-listed structured proposals, and the server alone validates/applies the one v1 social commitment. Phaser remains the client and gains a generic free-text dialogue panel plus minimal talk/travel/intervention controls.

**Tech Stack:** Python 3.12, FastAPI, SQLite, pytest, OpenAI Responses API (optional at runtime; never required by automated tests), Phaser 3.90, TypeScript 5.9, Vite 7, Playwright 1.55.

**Spec:** `docs/superpowers/specs/2026-09-02-living-npc-v1-design.md`

## Global Constraints

- Keep `GameService`, `LivingWorldService`, SQLite and canonical actions as the only authority for physical world state.
- Do not migrate to Godot in this milestone.
- Do not add combat, procedural quest generation, map expansion, NPC-to-NPC generated dialogue, rumor propagation, autonomous LLM planning, voice, vector DB/RAG or automatic sentiment-based relation mutation.
- `POST /api/dialogue` must remain backward compatible: omitting `npc_id` still talks to `npc_oren`.
- LLM/provider output may never directly move actors, create/remove items, transfer currency, complete quests or mutate Living World runtime.
- The only new generated social side effect in v1 is `remember_commitment:bring_useful_wood_to_mira`, server-validated against Mira's active wood request.
- Automated tests must not require `OPENAI_API_KEY`.
- Preserve PR #38 autonomous playtest instrumentation and do not merge `main` or PR #38 without separate user authorization.

---

### Task 1: Persistent dialogue storage and static NPC profiles

**Files:**
- Modify: `src/samseberpg/db.py`
- Create: `src/samseberpg/npc_profiles.py`
- Modify: `tests/test_database.py`
- Create: `tests/test_npc_profiles.py`

**Interfaces:**
- Produces `dialogue_turns` table keyed by world/NPC/player and ordered by `id`/`created_at`.
- Produces `NpcProfile` dataclass and `get_npc_profile(npc_id: str) -> NpcProfile` for `npc_oren`, `npc_mira`, `npc_kaspar`.
- Unknown profile IDs raise `LookupError`.

- [ ] **Step 1: Write failing database/profile tests**

Add tests that initialize a fresh database and assert `dialogue_turns` exists with columns `npc_actor_id`, `player_actor_id`, `user_text`, `npc_text`, `proposal_json`, `used_fallback`, `created_at`; add profile tests asserting all three profiles are distinct and unknown IDs raise.

```python
def test_dialogue_turns_schema_exists(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    with db.connect() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(dialogue_turns)")}
    assert {"npc_actor_id", "player_actor_id", "user_text", "npc_text", "proposal_json", "used_fallback", "created_at"} <= columns


def test_profiles_cover_three_living_npcs() -> None:
    assert get_npc_profile("npc_oren").display_name == "Орен"
    assert get_npc_profile("npc_mira").display_name == "Мира"
    assert get_npc_profile("npc_kaspar").display_name == "Каспар"
    assert get_npc_profile("npc_mira").personality != get_npc_profile("npc_kaspar").personality
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
pytest tests/test_database.py tests/test_npc_profiles.py -q
```

Expected: failures because the table/module do not yet exist.

- [ ] **Step 3: Add the minimal schema and profile module**

Add to `_SCHEMA`:

```sql
CREATE TABLE IF NOT EXISTS dialogue_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id TEXT NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    npc_actor_id TEXT NOT NULL REFERENCES npcs(actor_id) ON DELETE CASCADE,
    player_actor_id TEXT NOT NULL REFERENCES players(actor_id) ON DELETE CASCADE,
    user_text TEXT NOT NULL,
    npc_text TEXT NOT NULL,
    proposal_json TEXT NOT NULL DEFAULT '{}',
    used_fallback INTEGER NOT NULL DEFAULT 0 CHECK (used_fallback IN (0, 1)),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dialogue_turns_pair
ON dialogue_turns(npc_actor_id, player_actor_id, id DESC);
```

Create `NpcProfile` with fields `npc_id`, `display_name`, `role`, `personality`, `speech_style`, `motivations`, `knowledge_boundaries`; define exactly three initial profiles and `get_npc_profile`.

- [ ] **Step 4: Re-run focused tests and verify GREEN**

```bash
pytest tests/test_database.py tests/test_npc_profiles.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/samseberpg/db.py src/samseberpg/npc_profiles.py tests/test_database.py tests/test_npc_profiles.py
git commit -m "feat: add Living NPC profiles and dialogue history schema"
```

---

### Task 2: Generalize dialogue context to Oren, Mira and Kaspar with bounded knowledge

**Files:**
- Modify: `src/samseberpg/dialogue.py`
- Modify: `tests/test_dialogue.py`

**Interfaces:**
- `DialogueService.talk(player_id: str, user_text: str, npc_id: str = "npc_oren") -> DialogueDecision`
- `DialogueService.build_context(player_id: str, user_text: str = "", npc_id: str = "npc_oren") -> DialogueContext`
- `DialogueContext` exposes profile, location/activity/runtime state, full six-field relation vector, same-NPC memories, last six same-NPC dialogue turns, co-located visible actors/entities, and recent own world events.
- Private conversation with one NPC must never enter another NPC's context.

- [ ] **Step 1: Write failing three-NPC context tests**

Cover:

```python
def test_mira_context_reads_runtime_state_and_not_oren_private_history(...): ...
def test_kaspar_context_reads_goal_and_carrying_state(...): ...
def test_dialogue_context_contains_full_relation_vector(...): ...
def test_recent_history_is_pair_scoped_and_limited_to_six(...): ...
def test_unknown_npc_is_rejected(...): ...
def test_player_must_be_colocated_with_npc_to_talk(...): ...
```

For knowledge isolation, persist a Mira/player turn directly through the service, then build Kaspar context and assert the Mira text is absent.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
pytest tests/test_dialogue.py -q
```

Expected: failures because current code is hard-wired to `npc_oren` and only exposes trust/quest/memories.

- [ ] **Step 3: Implement generic context building**

Replace Oren constants in context construction with `npc_id`; load:

```python
SELECT npcs.role, npcs.current_activity, actors.location_id
FROM npcs JOIN actors ON actors.id = npcs.actor_id
WHERE npcs.actor_id = ?
```

Validate player and NPC are co-located before generating dialogue. Load the six relation fields for `(npc_id, player_id)`. Load only `npc_memories` for `(npc_id, player_id)`. Load last six `dialogue_turns` for the same pair. Load co-located actors/entities and recent `world_events WHERE actor_id = ?`. Parse `npc_runtime_state.state_json` only for the current NPC. Oren alone receives quest state; Mira receives `wood_stock/requested_wood`; Kaspar receives `goal/carrying_wood`.

- [ ] **Step 4: Keep prompt rendering explicit and bounded**

`DialogueContext.to_prompt()` must serialize only those fields. Include a line such as:

```text
knowledge_rule: You know only the supplied facts. Missing facts are unknown to you.
```

Do not include global `world_pulse` or other NPCs' private memories/history.

- [ ] **Step 5: Re-run dialogue tests**

```bash
pytest tests/test_dialogue.py -q
```

Expected: PASS for generic context, location validation and knowledge isolation while preserving old Oren tests.

- [ ] **Step 6: Commit**

```bash
git add src/samseberpg/dialogue.py tests/test_dialogue.py
git commit -m "feat: ground dialogue in NPC-scoped Living World context"
```

---

### Task 3: Persist turns and add the single validated Mira commitment

**Files:**
- Modify: `src/samseberpg/dialogue.py`
- Modify: `tests/test_dialogue.py`

**Interfaces:**
- `DialogueDecision` gains `npc_id: str` and `social_action: str | None` while retaining `text`, `proposal`, `used_fallback`.
- Allowed social action constant: `REMEMBER_MIRA_WOOD_COMMITMENT = "remember_commitment:bring_useful_wood_to_mira"`.
- Every successful/fallback dialogue writes one `dialogue_turns` row.
- Applying the commitment writes normalized durable memory for Mira/player but does not modify wood/request/runtime state.

- [ ] **Step 1: Write failing persistence and validation tests**

Add tests for:

```python
def test_dialogue_turn_persists_across_service_instances(...): ...
def test_mira_commitment_is_remembered_only_when_request_active(...): ...
def test_mira_commitment_does_not_resolve_physical_wood_request(...): ...
def test_forbidden_social_action_falls_back_without_mutation(...): ...
def test_commitment_for_oren_or_kaspar_is_rejected(...): ...
```

Advance Living World to a state where Mira requests wood before testing accepted commitment.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
pytest tests/test_dialogue.py -q
```

- [ ] **Step 3: Extend provider schema and decision validation**

OpenAI structured output must contain:

```json
{
  "text": "string",
  "proposal": "offer_quest:bring_5_firewood | none",
  "social_action": "remember_commitment:bring_useful_wood_to_mira | none"
}
```

The service validates both fields; unsupported values trigger deterministic fallback.

- [ ] **Step 4: Apply commitment server-side only after authoritative validation**

Accept only when `npc_id == "npc_mira"` and parsed Mira runtime has `requested_wood == true`. Insert-or-reinforce an `npc_memories` fact with normalized wording such as:

```text
The player promised Mira to bring useful wood while her workshop was blocked.
```

Do not call `LivingWorldService.give_resource` and do not change `wood_stock`/`requested_wood`.

- [ ] **Step 5: Persist every resolved turn**

After provider validation or fallback resolution, write one `dialogue_turns` row with serialized proposal/social-action metadata and fallback flag. Use SQLite-generated UTC timestamp so the persistence survives service recreation.

- [ ] **Step 6: Re-run focused tests**

```bash
pytest tests/test_dialogue.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/samseberpg/dialogue.py tests/test_dialogue.py
git commit -m "feat: persist Living NPC conversations and commitments"
```

---

### Task 4: Generalize the FastAPI dialogue contract and expose minimal Living NPC navigation/intervention state

**Files:**
- Modify: `src/samseberpg/api.py`
- Modify: `tests/test_api.py`
- Create or modify: `tests/test_player_intervention.py`

**Interfaces:**
- `DialogueRequest.npc_id: str = "npc_oren"`.
- `/api/dialogue` calls `dialogue.talk(player_id, text, npc_id)`.
- `/api/state/{player_id}` adds `living_npc` projection containing current tick, adjacent locations, co-located NPC IDs, Mira/Kaspar actionable state and driftwood ownership/location sufficient for the current client.
- Existing `world_pulse`, quest and legacy Oren fields remain unchanged.

- [ ] **Step 1: Write failing API tests**

Cover:

```python
def test_dialogue_defaults_to_oren_for_legacy_request(...): ...
def test_dialogue_accepts_explicit_mira_and_kaspar(...): ...
def test_dialogue_rejects_remote_npc(...): ...
def test_state_projects_adjacent_locations_and_living_npc_state(...): ...
def test_give_driftwood_to_mira_still_uses_canonical_action_api(...): ...
```

- [ ] **Step 2: Run API tests and verify RED**

```bash
pytest tests/test_api.py tests/test_player_intervention.py -q
```

- [ ] **Step 3: Implement compatible API changes**

Add `npc_id` default to request model, call generic service, and add a read-only projection helper. Projection must query existing canonical tables only; it must not introduce duplicate mutable state.

Suggested response shape:

```json
{
  "living_npc": {
    "tick": 3,
    "adjacent_locations": [{"id":"village_square","name":"Village Square"}],
    "nearby_npc_ids": ["npc_mira"],
    "mira": {"location_id":"workshop_yard","wood_stock":0,"requested_wood":true},
    "kaspar": {"location_id":"river_edge","goal":"collect_wood_for_mira","carrying_wood":0},
    "driftwood": {"location_id":"river_edge","owner_actor_id":null}
  }
}
```

- [ ] **Step 4: Re-run focused API/intervention tests**

```bash
pytest tests/test_api.py tests/test_player_intervention.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/samseberpg/api.py tests/test_api.py tests/test_player_intervention.py
git commit -m "feat: expose generic Living NPC API contract"
```

---

### Task 5: Add generic free-text dialogue and canonical intervention controls to the Phaser client

**Files:**
- Modify: `web/src/api.ts`
- Modify: `web/src/ui/DialoguePanel.ts`
- Modify: `web/src/main.ts`
- Modify: `web/src/styles.css`
- Modify: `web/tests/api-contract.test.ts`
- Create: `web/tests/living-npc-ui.test.ts`
- Modify: `web/package.json` only if the new node test file must be added explicitly to `test:contract`.

**Interfaces:**
- `GameApi.dialogue(playerId, npcId, text)` sends `npc_id`.
- `GameApi.action` union adds `GIVE` and `recipient_id`.
- `GameSnapshot.living_npc` maps the server projection.
- `DialoguePanel.openNpc(npcId, initialText?)` renders transcript + text input + send/close controls.
- Current `openOren()` may remain as a compatibility wrapper calling `openNpc("npc_oren", ...)`.

- [ ] **Step 1: Write failing TypeScript contract/UI tests**

Assert explicit Mira dialogue payload includes `npc_id`, action payload supports `GIVE` with `recipient_id`, and the dialogue panel creates an input/send path without hard-coding Oren as the title.

- [ ] **Step 2: Run contract tests and verify RED**

```bash
cd web
npm test -- --runInBand
npm run test:contract
```

If the package has no generic `npm test`, run only `npm run test:contract`; expected failure is missing Living NPC fields/methods.

- [ ] **Step 3: Extend the API client types and payloads**

Add `LivingNpcProjection`, `NpcDialogueDecision`, `recipient_id`, `GIVE`, and mapping/validation for optional `living_npc`. Keep old state fields intact.

- [ ] **Step 4: Refactor `DialoguePanel` to a real free-text conversation surface**

Maintain a bounded in-panel transcript array. Render NPC display name, transcript, `<input>` or `<textarea>`, `Отправить`, `Закрыть`. On send, call `api.dialogue(playerId, npcId, text)`, refresh state and append reply. Preserve contextual Oren quest buttons only for Oren and only when currently valid.

- [ ] **Step 5: Add minimum Living NPC controls to the existing World Pulse/HUD**

Render:

- co-located NPC buttons `Поговорить: Мира/Каспар/Орен`;
- adjacent canonical travel buttons using `MOVE`;
- `Подобрать корягу` only when player is at `river_edge` and driftwood is there;
- `Отдать корягу Мире` only when player is co-located with Mira and owns driftwood;
- existing `WAIT` controls remain.

All mutations must call existing `/api/action`; no client-side state fabrication.

- [ ] **Step 6: Re-run contract/type/build tests**

```bash
cd web
npm run typecheck
npm run test:contract
npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web/src/api.ts web/src/ui/DialoguePanel.ts web/src/main.ts web/src/styles.css web/tests web/package.json
git commit -m "feat: make Living NPC dialogue playable in browser"
```

---

### Task 6: Add deterministic Living NPC acceptance and autonomous browser routes

**Files:**
- Create: `tests/test_living_npc_acceptance.py`
- Modify: `web/tests/vertical-slice.spec.ts` or the existing canonical Playwright spec that currently owns PR #38 autonomous routes.
- Modify: `docs/release/AUTONOMOUS_PLAYTEST_V1.md` to document Living NPC evidence.

**Interfaces:**
- Backend acceptance uses a deterministic fake provider; no network/API key.
- Primary route: Mira request -> free dialogue -> persisted commitment -> take driftwood before Kaspar -> canonical GIVE -> follow-up dialogue -> persistence -> Kaspar knowledge isolation.
- Alternate route: no intervention -> time advances -> Kaspar independently resolves Mira request -> dialogue reflects resolved state.

- [ ] **Step 1: Write failing backend acceptance test**

Use a recording/fake provider that inspects contexts and returns explicit deterministic replies/actions. Assert:

```python
assert mira_context.runtime_state["requested_wood"] is True
assert commitment_memory_exists
assert give_result.success
assert reloaded_mira_context.runtime_state["requested_wood"] is False
assert private_mira_text not in kaspar_context.recent_dialogue_text
```

- [ ] **Step 2: Run backend acceptance and verify RED**

```bash
pytest tests/test_living_npc_acceptance.py -q
```

- [ ] **Step 3: Fix only missing product behavior found by the acceptance test**

Do not add new systems. Repair context/persistence/action wiring until the deterministic acceptance route passes.

- [ ] **Step 4: Extend Playwright canonical route**

Automate browser interactions through visible UI:

1. advance until Mira requests wood;
2. travel to Mira;
3. open Mira dialogue and send free text;
4. send a commitment phrase;
5. travel to river;
6. take driftwood;
7. return to Mira;
8. give driftwood;
9. talk to Mira again;
10. reload and verify state/dialogue remains usable;
11. talk to Kaspar and ensure no private-Mira transcript is rendered as Kaspar knowledge.

Add a separate deterministic no-intervention route that waits until Kaspar delivers.

- [ ] **Step 5: Run full local verification**

```bash
pytest -q
cd web
npm run typecheck
npm run test:contract
npm run build
npm run test:e2e
```

Expected: all existing tests plus Living NPC acceptance and browser routes PASS.

- [ ] **Step 6: Update autonomous playtest documentation**

Document the new evidence route, knowledge-isolation assertion, persistence assertion and distinction between social memory vs canonical physical mutations.

- [ ] **Step 7: Commit**

```bash
git add tests/test_living_npc_acceptance.py web/tests docs/release/AUTONOMOUS_PLAYTEST_V1.md
git commit -m "test: gate Living NPC social-world vertical slice"
```

---

### Task 7: Full regression, CI evidence and PR readiness

**Files:**
- No product files unless verification exposes a real defect.
- Update PR #39 body with verified evidence after all checks pass.

**Interfaces:**
- No merge.
- PR remains draft until evidence is green; user merge authorization is a separate future decision.

- [ ] **Step 1: Run complete backend suite from a clean environment**

```bash
pytest -q
```

Expected: all tests PASS.

- [ ] **Step 2: Run full web verification**

```bash
cd web
npm ci
npm run typecheck
npm run test:contract
npm run build
npm run test:e2e
```

Expected: all checks PASS with zero unexpected console/page errors in autonomous playtest report.

- [ ] **Step 3: Verify Windows compatibility path remains covered**

Push the branch and wait for the existing PR-triggered Windows compatibility workflow inherited from PR #38. Inspect workflow result; if RED, read failing job logs, reproduce/fix where possible, and rerun by pushing the corrective commit.

- [ ] **Step 4: Verify PR diff is scoped**

Compare `feat/autonomous-playtest-v1...feat/living-npc-v1`. Confirm no Godot migration, unrelated visual redesign, quest expansion or duplicate Living World engine entered the diff.

- [ ] **Step 5: Update PR #39 with evidence**

Record exact backend test count, TypeScript/contract/build result, Playwright route count, autonomous report verdict, Windows result, head SHA and remaining limitations. Keep PR draft and unmerged.

- [ ] **Step 6: Final verification-before-completion review**

Re-check the original spec success criterion against actual evidence. Do not claim Living NPC v1 complete unless the three-NPC dialogue, bounded knowledge, persistence, commitment, canonical intervention, alternate autonomous outcome and reload path are all evidenced.
