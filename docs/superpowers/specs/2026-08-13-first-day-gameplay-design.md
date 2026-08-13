# Pilot v0.1 — First Day Gameplay Design

## Product question

> Does a player enjoy living experimentally in a small systemic world when there is a reason to act, but no prescribed class or quest route?

The technical Behavior → Achievement → Ability loop already exists. The first-day layer turns it into a small playable situation for a 30–60 minute founder playtest.

## Chosen approach: soft life problem

The player is a newcomer in a tiny settlement. It is morning. They have no profession, 0 coins and no lodging.

By evening it would be useful to secure a bed at Oren's inn, but this is not a quest and is not mandatory. There is no game-over for ignoring it.

Oren's rule is simple:

- pay 3 coins; or
- explicitly ask for lodging when Mira or Kaspar trusts the player enough to vouch for them.

Asking Oren **about** lodging only explains the situation. It never spends coins or completes the goal automatically. Payment and social request are separate player choices.

The practical problem exists only to make the first actions meaningful. The product fantasy remains: **how the player chooses to live becomes the beginning of who they become**.

## First 60 seconds

The opening communicates only:

- newcomer to a small settlement;
- morning;
- 0 coins;
- no lodging;
- people live their own lives;
- the player may inspect and try actions.

It must not show optimal strategies, progression thresholds, a quest log, classes, or a list of reward branches.

## World

Keep exactly three locations:

1. `workshop_yard` — Mira's workshop yard.
2. `village_square` — Oren's inn and the square.
3. `river_edge` — riverbank where Kaspar spends the morning.

Keep exactly three NPCs and two ravens.

### Mira

- values different useful materials;
- `flat_stone` and `round_stone` are distinct useful contributions;
- `useful_wood` is another distinct contribution;
- first useful contributions can increase trust and sometimes pay coins;
- repeating the same contribution tag does not farm trust/money;
- later in the day she moves to the square.

### Oren

- controls lodging;
- explains the 3-coin / social-vouch alternatives;
- payment must be explicit;
- social request must be explicit;
- hitting the inn sign can reduce his trust.

### Kaspar

- values relevant natural finds;
- can build trust through useful contributions;
- moves from the river to the square later in the day.

### Ravens

Ravens have persistent state. Feeding with food raises trust. This is intentionally unnecessary for lodging, so it can reveal whether the player pursues a self-created interest.

## Player state

Only add what this experiment needs:

- location;
- inventory;
- `coins`, initially 0;
- `lodging_secured`, initially false;
- achievements/abilities already present.

Do not add health, hunger, thirst, attributes, level, equipment slots or classes.

## Time and independent world motion

`world_time` becomes meaningful:

- tick 0–3: morning;
- tick 4–7: day;
- tick 8–11: late day;
- tick 12+: evening.

`LOOK` is free. Most successful meaningful actions consume one tick. `WAIT` consumes the requested number of ticks.

At tick 8+, Mira and Kaspar move to `village_square`. The update is lazy: it occurs when the next game action is processed. No continuous background server is required.

The day does not hard-stop at evening.

## Canonical actions

Existing:

- LOOK
- MOVE
- TAKE
- DROP
- THROW
- WAIT

First-day additions:

- TALK
- GIVE
- FEED

### TALK

TALK is deterministic, not an LLM NPC chatbot.

Oren supports three canonical lodging intentions:

- `lodging` — information only;
- `pay_lodging` — explicitly spend 3 coins if available;
- `request_lodging` — explicitly ask for the social route if Mira/Kaspar trust >= 3.

This split protects player agency: curiosity cannot accidentally spend resources or resolve a goal.

### GIVE

An owned item can be given to a present NPC.

- the item leaves inventory;
- deterministic tag rules decide relevance;
- unique useful contributions can change trust/coins;
- repeat contribution tags give no repeat reward.

Bootstrap includes a small third Mira-relevant find, `driftwood_1` (`useful_wood`), at the river so the social lodging route is reachable organically after world movement.

### FEED

An owned food item can feed a present animal.

- food is consumed;
- raven trust persists;
- event is tagged `animal_care`;
- no automatic ability is promised from this in v0.1.

## Consequences

Freedom must alter state:

- useful gifts change trust/coins;
- feeding changes animal trust;
- sign hits can reduce Oren trust;
- duplicate contribution rewards are blocked;
- time moves NPCs;
- lodging state persists.

The existing optional throwing progression remains:

behavioral variety + competence → `hand_remembers_arc` → `aimed_throw`.

The UI must not instruct the player to grind for it.

## Relationship model

Only `trust` matters mechanically in this Pilot:

- 0 — stranger;
- 1–2 — positive familiarity;
- 3+ — enough trust to vouch for lodging;
- negative — distrust.

Do not add romance, jealousy, debts, factions or general social AI yet.

## Economy

Coins only create one practical alternative to the social route. This is not a full economy.

No shops, inflation, simulated prices, crafting economy or wages.

## Parser boundary

Both parsers may produce TALK/GIVE/FEED proposals.

The optional Ollama parser is constrained to:

- implemented action types;
- canonical lodging topics;
- entity IDs actually present in authoritative context.

Pipeline remains:

free text → parser proposal → CanonicalAction → GameService validation → deterministic state changes.

## Founder playtest signals

A good 30–60 minute session should produce several of these:

- at least five self-initiated “what if?” experiments;
- at least one self-created interest unrelated to lodging;
- visible independent world movement;
- at least one meaningful systemic consequence;
- at least two systems intersect naturally;
- lodging motivates action without becoming a quest checklist;
- after lodging is solved or ignored, the player still wants to continue;
- if progression unlocks, it feels causally tied to biography and invites another experiment.

## Failure signals

Stop and redesign rather than add content if:

- the first day becomes a linear 3-coin quest;
- NPCs feel like trust vending machines;
- most experiments end in “not implemented”;
- the only interesting part is free-text AI parsing;
- independent world changes are technically present but invisible in play;
- progression feels like hidden repetition counters;
- after lodging/progression there is no desire to continue.

## Explicitly out of scope

- combat;
- health/hunger/thirst;
- crafting;
- shops/full economy;
- quest/task log;
- factions/organizations;
- romance;
- LLM NPC dialogue;
- procedural quests;
- Discord;
- multiplayer concurrency;
- web UI;
- more locations/NPCs;
- second major progression branch.

## Technical boundaries

- `GameService` is the authoritative mutation boundary.
- schedules are deterministic/lazy.
- relationships/economy/lodging are ordinary code.
- meaningful outcomes append ActionEvent evidence.
- progression derives from behavior events, not a visible fixed skill tree.
- new behavior is test-first.

## Completion gate

> A founder can play one coherent first day for 30–60 minutes, understand the practical situation without a quest list, make different choices, experience persistent consequences and independent world motion, and potentially discover personalized progression.
