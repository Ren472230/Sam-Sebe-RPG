# Capital Project Audit — Sam-Sebe-RPG

Date: 2026-08-13
Branch audited: `feat/pilot-v0.1`
PR: #1

## Executive verdict

The project has a credible technical nucleus: deterministic authoritative state, a small persistent world, explicit event evidence, bounded LLM parsing, a first autonomous NPC chain, and unusually good scope discipline for an early experimental RPG.

However, the current Pilot is **not yet ready for a decision-quality founder playtest**. The main blockers are not missing content. They are experiment contamination, missing free-input evidence, weak player-facing visibility of autonomous world activity, a fragile/imbalanced first-day motivation loop, and several systemic consequence gaps that are likely to be hit by exactly the kind of "what if?" behavior the project wants to measure.

Recommendation: **do not add Living World v1, more NPCs, combat, economy, or a second major progression branch yet. Fix the P0 audit items first, run the founder playtest, then let evidence decide the next expansion.**

---

## What is strong

### 1. Scope discipline

The project consistently rejects premature MMO infrastructure, full economy, combat, quest systems, broad LLM agency, and large content expansion. That is the correct posture for a zero-budget hypothesis test.

### 2. Authoritative deterministic state

Game outcomes are ordinary code backed by SQLite. The LLM parser proposes canonical actions but does not write world state directly. Persistent RNG is deterministic. This is a strong foundation for debugging and future multiplayer authority.

### 3. Shared-state interaction

The player and Living World can compete for the same `driftwood_1`; Kaspar cannot fabricate it after the player takes it. Giving that same wood to Mira changes the same `wood_stock` used by the autonomous simulation. This is exactly the right systems-first direction.

### 4. Evidence separation

Player `action_events` and autonomous `world_events` are separated, preventing NPC activity from polluting player Behavior analysis. This is useful even though the combined timeline semantics still need work.

### 5. Regression coverage

The suite covers persistence, deterministic time stepping, social effects, progression, parser boundaries, demos, and player intervention in Living World. The weakness is not absence of tests; it is that most tests are scenario/regression tests rather than invariant/property tests.

---

# P0 — fix before founder playtest

## P0.1 — The interface contaminates the experiment

`help` lists almost the complete action vocabulary and also lists `прицельно бросить` before `aimed_throw` is unlocked.

This damages two measurements:

1. `WHAT_IF` is no longer reliably self-initiated if the interface has already suggested GIVE/FEED/THROW/etc.
2. the hidden progression is spoiled before discovery, because the future action variant is visible in the command list.

### Required fix

Split help by mode:

- **free-input founder mode:** only navigation/meta help (`look`, how to quit, possibly one example of natural-language input); never reveal action families or locked abilities;
- **systems/debug mode:** full canonical command reference;
- show `aimed_throw` syntax only after the ability is unlocked.

---

## P0.2 — The primary free-input hypothesis is almost unmeasured

`CanonicalAction` has `source_text`, but `action_events` do not persist it. Inputs that parse to `None` or fail because Ollama is unavailable are not recorded at all.

Therefore the database/report cannot answer:

- what the player actually typed;
- which inputs were unrecognized;
- how often rephrasing was needed;
- deterministic-parser vs Ollama usage;
- which canonical action was proposed;
- parser/model latency or errors;
- which natural-language intents systematically fail.

`failed_events` currently measures failed **GameService actions**, not failed player inputs.

### Required fix

Add a local-only `input_attempts` evidence table (or equivalent) containing at least:

- attempt id / world tick;
- raw text;
- parser mode (`deterministic`, `ollama`, `none`);
- model name when relevant;
- recognized boolean;
- proposed canonical action JSON;
- final result code when execution occurs;
- parser error class;
- optional latency.

This is measurement infrastructure, not analytics scope creep. It is required to evaluate the main product hypothesis.

---

## P0.3 — Living World exists in SQLite more than it exists for the player

Autonomous events are recorded in `world_events`, but normal CLI rendering only prints the player's `ActionResult`, entities for LOOK, and throw hit/miss data.

A player can be physically present while Mira works or requests wood and receive no ambient indication that this happened. The founder may therefore fail to notice Living World because of presentation, not because the simulation itself is uninteresting.

### Required fix

After each successful time-consuming action, return/render only **player-observable** autonomous events from the processed ticks:

- same-location events: directly visible;
- optionally adjacent/noisy events: short sensory hints;
- off-screen events remain hidden.

Do not print the global debug event log during play. Preserve uncertainty and discovery.

---

## P0.4 — The first-day alternatives are badly asymmetric

Current reward rules:

- Mira: `flat_stone` = +1 trust/+2 coins;
- Mira: `round_stone` = +1 trust/+2 coins;
- Mira: `useful_wood` = +1 trust;
- Kaspar: `pinecone` = +1 trust.

Lodging through trust requires Mira or Kaspar trust >= 3.

Consequences:

- the money route is extremely short: two obvious stones at the starting location already yield 4 coins, enough for 3-coin lodging;
- Mira's social route requires all three unique contributions;
- Kaspar's current content cannot reach trust 3 at all;
- if Kaspar collects the unique `driftwood_1` before the player, the Mira trust route becomes permanently unreachable in that world state.

This creates a hidden timed lockout for the social route while leaving the money route close to a linear starter quest.

### Required fix

Do not add more content. Rebalance the existing tiny system so both routes remain discoverable and reachable without an invisible race. Possible minimal solutions:

- lodging social route uses contextual trust/reputation >=2 plus a witnessed helpful act;
- Kaspar delivery to Mira can itself create a player-accessible social opportunity rather than permanently consuming the only third trust source;
- reduce the direct coin payout so two starting stones do not immediately solve the practical problem.

The exact numbers should serve the playtest, not become permanent balance.

---

## P0.5 — The first emergent ability has almost no positive utility

`aimed_throw` changes accuracy from 45% to 55%. In the current world, ordinary target hits mostly produce a hit/miss sentence. The only explicit systemic hit consequence is negative: hitting the inn sign reduces Oren's trust.

The founder protocol asks whether the player voluntarily reuses the new ability. At present, failure to reuse it may mean "there is nothing useful to do with accurate throwing," not "Behavior → Ability is uninteresting."

### Required fix

Add **one** positive systemic use for accuracy using existing entities/systems, not a new combat subsystem. Examples:

- knock a useful object down/reposition it;
- help an NPC with a precision task;
- safely interact with something at range.

One use is enough to make the progression test interpretable.

---

## P0.6 — Obvious violent experiments have almost no world reaction

THROW accepts any visible entity as a target. A hit only has a special consequence for `target_sign`.

Therefore a player can hit Mira, Kaspar, Oren, or a raven and receive a hit sentence without corresponding trust/fear/social state change.

For a project whose North Star is systemic response to experimentation, this is a likely trust-breaking moment.

### Required fix

Do not add health/combat. Add minimal consequence adapters:

- NPC hit -> trust penalty / refusal / short reaction state;
- raven hit -> fear increase / trust loss / possible movement.

This is consequence consistency, not combat scope.

---

# P1 — fix before Living World v1 / mechanic generation

## P1.1 — Event time semantics are inconsistent

Most time-consuming actions call `_record(...)` before `day.advance(...)`, so their `action_events.world_time` is the action's starting tick.

`WAIT` does the opposite: it advances all ticks first and records the WAIT event at the final tick.

The same column therefore mixes start-time and completion-time semantics.

This will become a serious problem for causal timelines, replay/debugging, multiplayer ordering, and analysis.

### Required fix

Choose one explicit model, for example:

- `started_at_tick` and `resolved_at_tick`; or
- all action events are completion events, with an optional duration;
- autonomous events get deterministic per-tick ordering.

Document the rule and test it.

---

## P1.2 — NPC knowledge is currently omniscient/telepathic

Each tick evaluates Mira first and Kaspar second. Mira can set `requested_wood=true` at the workshop, then Kaspar at the river immediately reads that global flag in the same tick and acts on it.

There is no communication, co-location, message, perception, or knowledge transfer.

This is acceptable for proving state-driven autonomy once, but it is the wrong foundation for multiple social agents: they will all become omniscient readers of global truth.

### Required fix

Before adding more autonomous goals, introduce the smallest possible distinction between:

- **world truth**;
- **what an agent currently knows**.

This does not require LLM memory or a vector DB. A small message/knowledge record with `fact`, `known_by`, `observed_at`, and `source` is enough for the next stage.

---

## P1.3 — Living World v0 is intentionally one-shot and then stalls

After Kaspar collects `driftwood_1`, the item location becomes NULL. Delivery turns it into Mira's abstract `wood_stock`. Mira consumes that stock, requests wood again, but the physical resource no longer exists at the river.

The second cycle therefore stalls permanently unless the player changed the first cycle.

The spec explicitly puts resource respawn out of scope, so this is spec-compliant. The problem is product-test reliability: a 30–60 minute session may get only one autonomous chain, and the player can miss it.

### Required fix

Do not build a full resource ecology. For the next test, provide at least one repeatable or second autonomous opportunity with existing systems so Living World can be noticed more than once.

---

## P1.4 — Item ownership/containment is ambiguous

`entities.location_id = NULL` currently means several different things:

- item is in player inventory (tracked separately);
- item is carried by Kaspar (tracked in Kaspar JSON state);
- item was given/consumed and is effectively gone.

This ambiguity is manageable for one resource but will fail quickly with more NPC inventory, theft, trade, multiplayer, or persistence debugging.

### Required fix

Before expanding item interactions, introduce one authoritative containment model (for example `holder_id/container_id` with explicit world location vs holder semantics) usable by player and NPCs.

---

## P1.5 — `MechanicValidator` is not yet a safe generic mechanic compiler boundary

The validator enforces primitive membership and numeric caps for several numeric primitives. Several primitives have no value validation at all, and the validator does not generally validate action names, variants, or condition structure.

It is safe enough for the current hand-authored `aimed_throw`, because the consumer additionally checks `THROW/aimed`. It is **not** sufficient to accept future LLM-generated mechanics safely.

### Required fix

Keep mechanic generation disconnected until each primitive has a typed schema and validator, including:

- legal value type/range;
- legal action family;
- legal variant;
- typed condition AST / whitelist;
- stacking/conflict rules.

Do not evaluate arbitrary condition strings.

---

## P1.6 — Persistence has no real migration/version contract

`initialize()` creates missing tables and `bootstrap_if_empty()` merges some missing JSON keys into old saves. This is useful but not a migration system.

There is no schema/world version and no ordered migration history. A future renamed column, changed invariant, or transformed entity state will be difficult to upgrade reliably.

### Required fix

Add a tiny integer schema version in `world_meta` and explicit migrations before the next structural DB change.

---

## P1.7 — No repository CI quality gate

The PR has no status checks/workflow runs. Tests are being verified locally, but GitHub currently does not enforce even `pytest` on the branch.

### Required fix

Add a zero-cost GitHub Actions workflow for:

- Python 3.12+;
- `pytest -q`;
- `python -m compileall -q src scripts`;
- optionally Ruff formatting/linting.

A coverage percentage gate is not necessary yet; invariant quality matters more than raw coverage.

---

## P1.8 — Tests are strong regressions but weak simulation invariants

Current Living World tests prove the known Mira/Kaspar sequence, persistence, intervention, and WAIT determinism. They do not broadly prove invariants under arbitrary action sequences.

### Required invariant tests

At minimum:

- one item cannot simultaneously be world-visible and owned/carried;
- no resource is duplicated by any sequence;
- each NPC performs at most one autonomous action per tick;
- world time never decreases;
- `WAIT N` equivalence holds for multiple N / states;
- failed player actions do not mutate authoritative state except failure evidence;
- transaction rollback leaves both state and event logs coherent on resolver failure.

Property-based tooling is optional; deterministic parameterized tests are enough for now.

---

## P1.9 — Design documentation has drifted

The first-day design spec still says Mira/Kaspar move to the square at tick 8+, while Living World v0 and the current code explicitly removed that teleport.

The README reflects the new truth, but one canonical design spec does not.

### Required fix

Mark superseded rules explicitly or update the first-day spec with a dated amendment. Future autonomous work must have one canonical source of truth.

---

# P2 — real debt, but safe to defer

## P2.1 — `BehaviorAnalyzer` is one handcrafted detector, not yet a general engine

The current analyzer only aggregates throwing evidence and the progression service hardcodes one achievement/ability threshold. This is fine for the first hypothesis test, but naming/documentation should avoid implying that a general Behavior-to-Mechanic Engine already exists.

Do not generalize until the first branch produces positive player evidence.

## P2.2 — `game_base.py` remains a large action monolith

The wrapper keeps Living World changes isolated, which was a good safety move. When a second independent behavior/progression/social subsystem is added, split action resolvers by responsibility rather than continuing to grow the base class.

## P2.3 — `state_json` is flexible but weakly typed

Useful for the pilot, dangerous if every new mechanic adds ad-hoc keys. Add typed accessors/dataclasses when a second NPC starts sharing the same state shape, not before.

## P2.4 — Day pacing is only a label

At tick 12 the world becomes `evening` forever. For the current first-day experiment this is acceptable, but it should not quietly become the permanent time model.

---

# Security / safety review

No high-severity application-security issue was identified in the reviewed pilot scope.

Positive properties:

- SQL values are parameterized in gameplay paths;
- no dynamic `eval`/`exec` mechanism was found;
- no pickle/deserialization path was found;
- runtime has no third-party production dependencies;
- LLM output goes through canonical-action and authoritative GameService validation;
- unknown entity IDs are rejected by the LLM parser boundary.

Caveats for later stages:

- `--ollama-url` can point somewhere other than localhost, so do not promise local-only/privacy properties without enforcing or clearly surfacing endpoint choice;
- SQLite is currently single-user architecture; multiplayer concurrency needs a separate explicit design rather than simply exposing this DB to multiple clients.

---

# Product interpretation

## What the current build can honestly validate

- whether a small systemic situation encourages experimentation;
- whether deterministic NPC-caused state changes feel more alive than static NPCs;
- whether one handcrafted behavioral specialization feels causally connected to play;
- whether local free-text parsing over a **small canonical action vocabulary** is tolerable.

## What it cannot yet validate

- the North Star claim that a player can "try almost anything";
- a general Behavior-to-Mechanic Engine;
- a scalable Living World agent architecture;
- multiplayer social dependence;
- sustainable long-session world life;
- market retention or monetization.

Treating those as already proven would be the largest strategic mistake available at this stage.

---

# Recommended repair sequence

## Audit Fix Pack A — make the founder test valid

1. Split debug help from founder/free-input help; hide locked ability syntax.
2. Add `input_attempts` telemetry and parser outcome reporting.
3. Standardize event timing semantics.
4. Surface player-observable autonomous events after ticks.
5. Rebalance lodging routes so money is not trivial and trust is not silently lockable.
6. Add minimal reactions to hitting NPCs/animals.
7. Give `aimed_throw` one positive systemic use.
8. Update the stale first-day design spec.
9. Add CI.

Then run the founder playtest.

## Audit Fix Pack B — only after a positive founder signal

1. Minimal NPC knowledge/message model.
2. Explicit item holder/container model.
3. Schema migrations/versioning.
4. Primitive-specific MechanicValidator schemas.
5. Stronger simulation invariants.
6. Only then consider a second autonomous loop or second behavior branch.

---

# Go / no-go gates

### Founder playtest now

**NO-GO** until Audit Fix Pack A is complete. The current test can produce misleading evidence for the wrong reasons.

### Add Living World v1 now

**NO-GO.** Current v0 is enough to test the idea once the presentation/measurement defects are repaired.

### Add generic LLM mechanic generation now

**NO-GO.** The current validator is not a complete generic safety contract.

### Continue the project

**GO.** There is no architectural reason to abandon the project. The current weaknesses are concentrated, understandable, and fixable without expanding scope.

The next useful unit of work is not new content. It is **Audit Fix Pack A → founder playtest → evidence-based decision**.