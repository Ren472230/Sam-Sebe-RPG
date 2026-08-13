# Pilot v0.1 — First Day Gameplay Design

## Product question

The first playable design must answer one question before we expand the world:

> Does a player enjoy living experimentally in a small systemic world when there is a reason to act, but no prescribed class or quest route?

The existing vertical slice already proves the technical Behavior → Achievement → Ability loop. This design turns that slice into a small game situation suitable for a 30–60 minute founder playtest.

## Chosen approach

Use a **soft life problem**, not a quest chain and not survival pressure.

The player is a newcomer in a tiny settlement. It is morning. They have no profession and almost no standing with the locals. By evening they would like to secure a place to sleep at Oren's inn.

Oren does not give a quest list. He simply has a rule: lodging costs 3 coins, or a local who trusts the player enough can vouch for them.

The player may ignore this goal completely. Sleeping outside is allowed. There is no game-over and no forced route.

This gives the player a reason to inspect the world while preserving the core fantasy: **how they decide to live becomes the beginning of who they become**.

## First 60 seconds

The first screen should communicate only:

- the player has arrived in a small settlement;
- it is morning;
- they have 0 coins and no lodging;
- evening will come as actions consume time;
- Oren at the square can explain lodging;
- the game accepts commands/actions rather than offering a quest menu.

It must not list optimal strategies, progression branches, achievements, or every possible interaction.

The player should immediately be able to `look`, move, talk, pick things up, give things, feed animals, throw objects, or wait.

## World

Keep the existing three locations:

1. `workshop_yard` — Mira's workshop yard.
2. `village_square` — Oren's inn and the village square.
3. `river_edge` — riverbank where Kaspar spends much of the day.

Keep three NPCs and two ravens. Do not add more characters for this pilot.

### NPC roles

**Mira, craftswoman**
- values useful unusual materials;
- appreciates different kinds of stones rather than endless copies of the same thing;
- can reward a useful first contribution with coins and trust;
- spends the morning at the workshop and later moves to the square.

**Oren, innkeeper**
- controls lodging;
- offers a bed for 3 coins;
- also accepts a social route when another local trusts the player enough to vouch for them;
- reacts negatively if the player repeatedly damages or attacks inn property.

**Kaspar, forager**
- spends the morning near the river and later returns to the square;
- values useful natural finds;
- can build trust through relevant gifts.

### Ravens

Ravens have persistent `trust` and `fear` state.

Feeding them with food raises trust. This is intentionally not required for lodging. It exists to test whether players pursue self-created interests even when those interests do not advance the obvious practical goal.

## Player state

Add only what the first-day design needs:

- `coins`, initially 0;
- `lodging_secured`, initially false;
- current location;
- inventory;
- existing achievements and abilities.

Do not add hunger, thirst, health, level, experience, attributes, equipment slots, or character classes.

## Time and persistent world

`world_time` becomes meaningful game time.

- The day begins at tick 0 (morning).
- Most successful meaningful actions consume 1 tick.
- `LOOK` does not consume time.
- `WAIT` consumes the requested number of ticks.
- At later ticks NPC schedules update lazily when the game processes the next action.
- Mira and Kaspar can move to the square later in the day without the player causing that movement.

This is enough to demonstrate that the world changes independently without implementing a continuous background server.

The pilot does not hard-stop at evening. The UI simply reports that evening has arrived and whether lodging is secured.

## Canonical actions

Keep existing actions:

- LOOK
- MOVE
- TAKE
- DROP
- THROW
- WAIT

Implement the already reserved actions:

- TALK
- GIVE
- FEED

### TALK

`TALK` is deterministic in v0.1. It is not an AI chatbot.

It returns a short state-aware response based on NPC identity, world time, relationship, and an optional topic.

Important topic for Oren: `lodging`.

If the player asks Oren about lodging:
- with at least 3 coins, the player can pay 3 coins and secure lodging;
- otherwise, if Mira or Kaspar trust is at least 3, Oren accepts the social vouch and secures lodging;
- otherwise Oren explains the rule without giving a quest checklist.

### GIVE

The player can give an owned item to an NPC at the same location.

- the item leaves player inventory and is removed from immediate world availability;
- relevant first-time contributions may increase trust and award coins;
- repeating the same contribution must not produce unlimited money or trust.

For the pilot, NPC preference rules are deterministic and tag-based.

### FEED

The player can feed a raven with an owned item tagged `food`.

- the food is consumed;
- raven trust increases;
- the event receives behavior tags such as `animal_care`;
- no guaranteed mechanical ability is added in this design.

The point is to record whether the player chooses to build a relationship with animals without being instructed to do so.

## Consequences

Freedom must create consequences, not just parser acknowledgement.

At minimum:

- valued gifts can change NPC trust and coins;
- feeding changes raven trust;
- hitting Oren's inn sign with thrown objects can reduce Oren's trust;
- the same exploit/reward cannot be farmed infinitely;
- world time changes NPC positions;
- securing lodging changes player state persistently.

The existing throwing progression remains intact:

behavioral variety + competence → `hand_remembers_arc` → `aimed_throw`.

This progression is optional. The game must never tell the player to grind throwing to unlock it.

## Relationship model

Reuse the existing `relations` table.

For this pilot only `trust` is mechanically important.

Trust is small and legible:

- 0 — stranger;
- 1–2 — positive familiarity;
- 3+ — enough trust to vouch for lodging;
- negative — distrust.

Do not build love, jealousy, fear networks, debts, factions, or general social AI yet.

## Economy

Economy is deliberately tiny.

Coins exist only to create one practical alternative to the social route.

No shops, price simulation, inflation, crafting economy, wages, or item marketplace.

The pilot only needs deterministic one-time rewards for useful contributions and the 3-coin lodging payment.

## Parser boundary

The deterministic parser and optional Ollama parser may produce `TALK`, `GIVE`, and `FEED` canonical actions.

The LLM still has no authority over outcomes:

free text → parser proposal → CanonicalAction → validation → deterministic GameService → state/event changes.

The parser must not invent entity IDs outside the current context.

## Founder playtest experience

A successful session is not defined by obtaining lodging.

A good 30–60 minute session should produce several of these signals:

- the player voluntarily asks "what happens if I..." and tries at least five unsuggested actions;
- the player notices that time/NPC positions change independently;
- at least two systems intersect in a meaningful way (item → NPC trust → lodging, behavior → ability → reuse, action → property/social consequence);
- the player pursues at least one self-created interest that is not necessary for lodging;
- an emergent ability, if unlocked, feels causally connected to the player's behavior;
- after obtaining or failing to obtain lodging, the player still wants to try something else.

## Failure signals

Stop and redesign rather than adding content if:

- the player treats NPC contributions as an obvious quest checklist;
- the only interesting thing remains the LLM parser;
- the player needs constant hints for what to do;
- the first day becomes a linear route for exactly 3 coins;
- free experiments mostly return "not implemented";
- relationships feel like invisible point farming;
- the player obtains the first ability but has no reason to test it.

## Explicitly out of scope

Do not add in this pass:

- combat;
- health/hunger/thirst;
- crafting;
- shops or full economy;
- quests/task log;
- factions/organizations;
- romance;
- LLM NPC dialogue;
- procedural quests;
- Discord;
- multiplayer concurrency;
- web UI;
- more locations or NPCs;
- a second generated mechanic branch unless playtest evidence demands it.

## Technical boundaries

- `GameService` remains the only authoritative state mutation path.
- NPC schedule updates are deterministic/lazy.
- relationship, economy, and lodging rules are ordinary code.
- all meaningful outcomes append `ActionEvent` evidence.
- progression continues to derive from events, not from a fixed visible skill tree.
- new rules must be covered by tests before implementation.

## Decision

Pilot v0.1 is no longer treated as complete merely because the Behavior Engine works.

The next completion gate is:

> **A founder can play one coherent first day in the settlement for 30–60 minutes, understand their practical situation without a quest list, make several different choices, experience persistent consequences, and potentially discover personalized progression.**
