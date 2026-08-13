# Pilot v0.1 — First Day Gameplay Design

Status: canonical after Living World v0 + Audit Fix Pack A (2026-08-13)

## Product question

> Does a player enjoy living experimentally in a small systemic world when there is a reason to act, but no prescribed class or quest route?

The first day exists to test player-directed experimentation, visible systemic consequences, autonomous world causality, and the first Behavior → Achievement → Ability branch in one small situation.

## Chosen approach: soft life problem

The player is a newcomer in a tiny settlement. It is morning. They have no profession, 0 coins and no lodging.

By evening it would be useful to secure a bed at Oren's inn, but this is not a quest and is not mandatory. There is no game-over for ignoring it.

Oren's rule:

- pay 3 coins; or
- explicitly ask for lodging when Mira or Kaspar trusts the player enough to vouch for them.

Asking Oren **about** lodging only explains the situation. Payment and social request remain separate explicit player choices.

## First 60 seconds and spoiler discipline

The opening communicates only:

- newcomer to a small settlement;
- morning;
- 0 coins;
- no lodging;
- people live their own lives;
- the player may inspect and try actions.

Founder mode must not expose:

- optimal routes;
- progression thresholds;
- action-family catalogue;
- locked abilities;
- quest log/classes/reward branches.

Systems mode exists for diagnostics and may show canonical commands. `aimed_throw` syntax is shown only after unlock.

## World

Exactly three locations:

1. `workshop_yard` — Mira's workshop yard.
2. `village_square` — Oren's inn and the square.
3. `river_edge` — riverbank and natural finds.

Exactly three NPCs and two ravens.

### Mira

- has persistent workshop state and real `wood_stock`;
- works autonomously through Living World v0;
- values distinct useful material tags;
- first `flat_stone` contribution: +1 trust, +1 coin;
- first `round_stone` contribution: +1 trust, +1 coin;
- first `useful_wood`: +1 trust, +0 coins;
- repeat contribution tags do not farm reward;
- does **not** teleport to the square at tick 8.

### Oren

- controls lodging;
- explains the 3-coin / social-vouch alternatives;
- payment and social request must be explicit;
- inn-sign vandalism can reduce his trust.

### Kaspar

- participates in Living World v0 resource delivery;
- first relevant `pinecone` contribution: +1 trust, +1 coin;
- moves because of autonomous resource work, not an old tick-8 schedule.

### Ravens

- persistent `trust` and `fear`;
- feeding food raises trust;
- being hit by a projectile raises fear, lowers trust and causes deterministic flight;
- these interactions remain optional for lodging.

## Superseded rule: tick-8 teleport

The original first-day draft said:

> At tick 8+, Mira and Kaspar move to `village_square`.

That rule is **superseded and no longer canonical**. Living World v0 owns Mira/Kaspar autonomous state and Kaspar movement. `DayService.apply_schedules()` no longer teleports them.

## Player state

Only what the experiment needs:

- location;
- inventory;
- `coins`, initially 0;
- `lodging_secured`, initially false;
- relationships;
- persistent animal/NPC state;
- achievements/abilities;
- local input-attempt evidence.

No health, hunger, thirst, attributes, levels, equipment slots or classes.

## Time semantics

`world_time` phases:

- tick 0–3: morning;
- tick 4–7: day;
- tick 8–11: late day;
- tick 12+: evening.

`LOOK` is free. Most successful meaningful actions consume one tick. `WAIT N` consumes N deterministic intermediate ticks.

For **new** `action_events`:

- `world_time` = resolved/completion tick;
- `started_at_tick` records action start;
- `resolved_at_tick` records action completion;
- `duration_ticks` records consumed ticks;
- failures and LOOK have duration 0;
- ordinary successful timed actions have duration 1;
- `WAIT N` has duration N.

Historical pre-audit events migrated to schema v2 are conservatively backfilled as duration 0 because exact historical duration cannot be reconstructed.

## Canonical actions

- LOOK
- MOVE
- TAKE
- DROP
- TALK
- GIVE
- FEED
- THROW
- WAIT

`USE` remains in the enum but is not implemented in the Pilot.

## TALK / lodging

TALK is deterministic, not an LLM NPC chatbot.

Oren topics:

- `lodging` — information only;
- `pay_lodging` — explicitly spend 3 coins if available;
- `request_lodging` — explicitly request the social route.

A local can vouch at **trust >= 2**.

This threshold is intentional for the current experiment: two distinct starter contributions can establish a social route, while those same two contributions produce only 2 coins and therefore do not trivially complete the money route.

## GIVE and mini-economy

An owned item can be given to a present NPC:

- it leaves inventory;
- deterministic tag rules decide relevance;
- unique useful contributions may change trust/coins;
- repeat tags do not repeat the reward.

Current Pilot reward geometry:

```text
Mira flat stone  -> +1 trust, +1 coin
Mira round stone -> +1 trust, +1 coin
Mira useful wood -> +1 trust, +0 coins
Kaspar pinecone  -> +1 trust, +1 coin
```

Therefore:

- two nearby starter stones give 2 coins, not enough for a 3-coin room;
- the same two distinct contributions give Mira trust 2 and make social vouch reachable;
- a money route still exists but naturally requires at least one additional contribution/exploration.

This is Pilot balance, not final economy design.

## Living World v0 intersection

Mira/Kaspar use the same physical `driftwood_1` as the player:

- Mira consumes workshop stock and creates a resource need;
- Kaspar reacts, collects the real shared wood if available, returns and delivers;
- player taking the wood first blocks Kaspar;
- player giving that wood to Mira satisfies the same `wood_stock` need;
- no parallel quest flag exists.

Only new autonomous events in the player's **current location** are attached to ordinary `ActionResult` feedback. Off-screen world events remain in `world_events` but are not exposed omnisciently.

This observability rule is intentionally strict for v0: the founder test should measure noticed local causality, not debug-log awareness.

## Consequence consistency

Freedom must alter state when an obvious supported action succeeds.

Existing and audited consequences include:

- gifts → trust/coins;
- feeding → animal trust;
- inn-sign hit → Oren trust -1;
- successful projectile hit on NPC → target trust -2 and persistent `hit_by_player_count`;
- successful hit on raven → fear +2, trust -1 and deterministic flight;
- duplicate gift rewards blocked;
- lodging persists;
- world time triggers autonomous state changes.

These hit reactions are social/animal consequences only. There is still no HP/combat system.

## Behavior → Achievement → Ability

The first branch remains hidden and optional:

```text
varied competent throwing
→ hand_remembers_arc
→ aimed_throw
```

Pilot unlock evidence remains accelerated:

- >=12 valid resolved throws;
- >=5 hits;
- >=3 targets;
- >=2 projectile types;
- >=2 locations.

`aimed_throw` adds +10 percentage points to throwing accuracy after persisted mechanic validation.

### Positive systemic use

An unlocked **aimed** hit on `target_barrel`, while Mira is present and the barrel is not already fixed, can knock a warped barrel detail back into place:

- `target_barrel.state.precision_fixed = true`;
- Mira trust +1 once;
- result/evidence exposes `precision_task_completed=true`.

This is deliberately one small positive use, not a quest or crafting branch. It prevents the first emergent ability from being experimentally meaningless.

## Parser boundary and input evidence

Pipeline:

```text
raw input
→ deterministic parser, then optional Ollama fallback
→ CanonicalAction proposal
→ GameService validation/outcome
→ deterministic state mutation
```

Ollama is constrained to canonical actions/topics and authoritative context IDs and never mutates SQLite directly.

Every gameplay input is also appended to local `input_attempts` evidence with parser mode/model, recognition status, proposed canonical action, result code, parser error and latency. This evidence does not influence game state.

## Founder playtest signals

A useful 30–60 minute session should reveal:

- at least five self-initiated “what if?” experiments;
- at least one self-created interest unrelated to lodging;
- visible independent world change;
- at least one meaningful systemic consequence;
- at least one desire to intervene in an autonomous NPC situation;
- at least two systems intersect naturally;
- lodging motivates without becoming a checklist;
- after lodging is solved/ignored, interest continues;
- free-input friction is measurable rather than invisible;
- if progression unlocks, it feels biographical and invites another practical experiment.

## Failure signals

Stop and redesign rather than add content if:

- the first day becomes a linear 3-coin quest;
- NPCs feel like trust vending machines;
- most player ideas become parser/system DEAD_ENDs;
- Living World exists in DB but remains invisible in play;
- consequences fail to change planning;
- progression feels like a hidden repetition counter;
- the ability unlock has no use players care about;
- after lodging/progression there is no desire to continue.

## Explicitly out of scope

- combat/HP;
- hunger/thirst;
- crafting;
- shops/full economy;
- task/quest log;
- factions/organizations/romance;
- LLM NPC dialogue/agency;
- procedural quests;
- Discord;
- multiplayer concurrency;
- web UI;
- more locations/NPCs/items;
- resource ecology/respawn;
- generic GOAP/utility planner;
- generic Mechanic Compiler;
- real-time catch-up while the program is closed.

## Technical boundaries

- `GameService` is authoritative.
- SQLite is canonical state.
- `action_events` and `world_events` are separate evidence streams.
- input telemetry is observational only.
- Living World v0 is deterministic.
- progression derives from player action evidence.
- new behavior is test-first and CI-gated.

## Completion gate

Technical completion means a founder can start a fresh schema-v2 world in founder mode, receive no catalogue spoilers, produce measurable input attempts, observe local autonomous consequences, reach either lodging route without a hidden driftwood prerequisite, encounter persistent reactions to obvious actions, and potentially discover a useful personalized ability.

That gate means **ready for founder playtest**, not that the product hypothesis is validated.