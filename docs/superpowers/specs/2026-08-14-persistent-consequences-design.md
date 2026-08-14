# Persistent Consequences — Design Specification

## Goal

Turn the shared-world kernel from a persistent inventory demo into a small world where an expressive action can visibly alter an object, affect an NPC relationship when witnessed, and leave evidence another player can inspect later.

The smallest proof is:

1. Player A owns a stone.
2. Player A moves to the village square.
3. Oren is present.
4. Player A throws the stone at the tavern sign.
5. The sign's condition changes canonically and the stone lands on the ground.
6. Oren's relation toward Player A worsens because he witnessed it.
7. Player B later looks at the square and sees the damaged sign.
8. Restart preserves the damage and relation state.

A positive social counterpart is GIVE: transferring a food item to a present NPC can improve that NPC's relation toward the giver.

## Scope

Included now:
- `THROW` and `GIVE` canonical action families;
- separate `item_id` and `target_id` in `CanonicalAction`;
- deterministic target damage from throwable items;
- entity-state visibility in `WorldView` and Discord rendering;
- witness-aware deterministic relation changes;
- structured event evidence for damage, witnesses and relation deltas;
- parser forms for explicit THROW/GIVE canonical syntax;
- cross-player visibility and restart persistence tests.

Deferred:
- hit RNG, stats, stamina and range;
- combat or throwing at actors;
- stealing/crime/guards;
- generic physics;
- arbitrary object destruction rules;
- BUY/USE/economy;
- progression unlocks;
- LLM parsing.

## Domain model changes

`ActionType` adds:
- `THROW`;
- `GIVE`.

`CanonicalAction` adds:
- `item_id: str | None`.

Existing TAKE/DROP continue to use `target_id` for backward compatibility. THROW/GIVE use `item_id` for the transferred/thrown object and `target_id` for the world object or actor being targeted.

`VisibleEntity` adds decoded `state: dict[str, Any]` so presentation can expose canonical object condition without directly querying SQLite.

## THROW rule v0

Preconditions:
- `item_id` exists and is owned by actor;
- target exists as an entity at actor's current location;
- item state contains `throwable=true`;
- target state contains integer `condition` from 0–100.

Success:
- deterministic damage is read from item state `impact_damage`, default 20;
- target condition becomes `max(0, before - damage)`;
- thrown item leaves inventory and is placed at actor's current location;
- event is appended atomically with state mutations.

Failures:
- `ITEM_NOT_OWNED`;
- `TARGET_NOT_FOUND`;
- `TARGET_NOT_PRESENT`;
- `ITEM_NOT_THROWABLE`;
- `TARGET_NOT_DAMAGEABLE`.

There is deliberately no miss chance yet. The hypothesis being tested is persistence and consequences, not combat accuracy.

## Witness rule v0

A witness is an NPC actor located at the action location at resolution time.

For the specific tavern-sign consequence:
- if `target_id == tavern_sign` and `npc_oren` is present, Oren's relation toward the acting player changes by:
  - trust `-3`;
  - conflict `+4`.

If Oren is not present, the sign is still damaged but no Oren relation delta is applied. This makes real-time NPC schedule materially relevant to consequences.

Relations are stored as `source_actor_id = npc`, `target_actor_id = player`. Missing rows are created with zero baselines before applying deltas.

## GIVE rule v0

Preconditions:
- `item_id` exists and is owned by actor;
- target actor exists at the same location;
- target actor is not the acting player.

Success:
- item ownership moves atomically from giver to target actor;
- if target is an NPC and item state contains `edible=true`, relation from that NPC toward the giver changes:
  - trust `+2`;
  - affinity `+1`.

Giving a non-food portable item is allowed but has no relation bonus. Player-to-player GIVE is allowed and has no automatic relationship mutation.

Failures:
- `ITEM_NOT_OWNED`;
- `TARGET_ACTOR_NOT_FOUND`;
- `TARGET_NOT_PRESENT`;
- `INVALID_TARGET`.

## Event evidence

`action_events.evidence_json` becomes meaningful gameplay evidence rather than always `{}`.

THROW success evidence:
```json
{
  "item_id": "stone_flat_1",
  "target_id": "tavern_sign",
  "damage": 20,
  "condition_before": 100,
  "condition_after": 80,
  "witnesses": ["npc_oren"],
  "relation_deltas": {
    "npc_oren": {"trust": -3, "conflict": 4}
  }
}
```

GIVE success evidence records item, target and any relation delta. Failures may record compact reason context but never invent changes.

This event structure is intentionally suitable for the later Behavior Engine.

## Presentation

Entity rendering exposes useful state without raw JSON noise. For an entity with `condition`, append a readable condition marker, for example:

`- Вывеска таверны (tavern_sign) — состояние: 80%`

The second player therefore perceives the first player's persistent consequence through ordinary `/look`.

## Parser forms

Explicit deterministic forms only:
- `бросить <item_id> в <target_id>`;
- `throw <item_id> at <target_id>`;
- `дать <item_id> <actor_id>`;
- `give <item_id> <actor_id>`.

The parser does not infer aliases such as “вывеска” yet. Free-form interpretation remains a later provider behind the same canonical action boundary.

## Testing

Required tests:
- THROW cannot use an unowned/non-throwable item;
- THROW cannot affect absent/non-damageable target;
- successful THROW damages sign, drops item, records evidence;
- Player B sees changed condition after Player A's THROW;
- Oren witnesses at 08:00 and relation changes;
- Oren absent in a controlled schedule state means no relation change;
- restart preserves damaged condition and relation;
- GIVE food to present NPC transfers ownership and improves relation;
- GIVE to absent actor fails without transfer;
- parser produces correct item/target IDs;
- Discord application can execute explicit THROW/GIVE text without bypassing GameService.

## Definition of Done

The slice is complete when a deterministic two-player scenario proves that Player A can damage the tavern sign with a thrown owned stone, Player B sees the persisted damage, witness presence changes Oren's canonical relationship state, a positive GIVE action can change an NPC relationship, structured event evidence records what happened, all changes survive restart, and all prior kernel/Discord tests remain green.
