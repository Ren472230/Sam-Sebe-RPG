# Minimal Economy + USE — Design Specification

## Goal

Add the smallest deterministic economic/resource loop that makes money and item state matter without building a full economy simulation.

Target scenario:

1. Player reaches the village square with 10 coins.
2. A bottle is visibly offered by Oren for 3 coins.
3. TAKE cannot bypass the sale.
4. BUY atomically transfers 3 coins to Oren and ownership of the bottle to the player.
5. Player USEs the owned bottle on the village well.
6. Bottle state changes from empty to filled with water.
7. `/me` exposes 7 coins and the filled bottle.
8. Restart preserves player money, Oren revenue and bottle state.

This is deliberately an economy *loop seed*, not a market system.

## Scope

Included:
- `BUY` and `USE` canonical actions;
- player coins exposed in `WorldView` and `/me`;
- NPC coin balance in canonical SQLite state;
- one explicit sale offer: `bottle_1`, seller `npc_oren`, price 3;
- TAKE protection for items marked for sale;
- one deterministic USE affordance: fill a fillable container from a water source;
- parser forms for BUY/USE;
- structured evidence and idempotency through existing action pipeline;
- restart persistence.

Deferred:
- SELL, negotiation, variable prices, supply/demand;
- multiple shop inventories;
- jobs/wages/taxes;
- hunger/thirst stats;
- generic crafting;
- arbitrary USE scripting;
- LLM interpretation.

## Canonical model

`ActionType` adds:
- `BUY`;
- `USE`.

Both use existing `item_id` + `target_id`:
- BUY: `item_id` is offered item; `target_id` is seller actor;
- USE: `item_id` is owned item; `target_id` is target world entity.

`WorldView` adds `coins: int` for the observing player.

## Canonical sale representation

The offered bottle remains a location entity so it is naturally visible through LOOK:

```json
{
  "price": 3,
  "for_sale_by": "npc_oren",
  "fillable": true,
  "filled_with": null
}
```

The well gains:

```json
{"water_source": true}
```

`TAKE` checks sale metadata before ownership transfer and returns `FOR_SALE_ONLY` for an offered item. This prevents free acquisition through a lower-level action.

## NPC money

`npcs` gains canonical integer `coins >= 0`. Oren starts with a small deterministic balance. BUY debits player and credits NPC in the same transaction as item ownership/event/idempotency.

No currency disappears on purchase.

## BUY v0

Preconditions:
- item exists at buyer's current location and is unowned;
- item state has positive integer `price` and `for_sale_by`;
- target actor matches `for_sale_by`;
- target is an NPC present at buyer's location;
- player has enough coins.

Success:
- buyer coins -= price;
- seller NPC coins += price;
- item becomes owned by buyer;
- event evidence records item, seller, price, buyer/seller balances before/after.

Failures:
- `TARGET_NOT_FOUND`;
- `TARGET_NOT_PRESENT`;
- `ITEM_NOT_FOR_SALE`;
- `WRONG_SELLER`;
- `SELLER_NOT_PRESENT`;
- `INSUFFICIENT_FUNDS`.

## USE v0

The first USE rule is intentionally data-driven but narrow.

Preconditions:
- item exists and is owned by actor;
- target entity exists at actor location;
- item state `fillable=true`;
- target state `water_source=true`;
- item is not already filled.

Success:
- item `filled_with` becomes `water`;
- event evidence records item, target and before/after fill state.

Failures:
- `ITEM_NOT_OWNED`;
- `TARGET_NOT_FOUND`;
- `TARGET_NOT_PRESENT`;
- `UNSUPPORTED_USE`;
- `ITEM_ALREADY_FILLED`.

This is a whitelist-style affordance, not arbitrary scripts embedded in JSON.

## Presentation

LOOK renders offer metadata when present:

`Пустая бутылка (bottle_1) — цена: 3 монеты`

`/me` renders:
- coin balance;
- inventory item state, including `filled_with` when meaningful.

Example:

`Пустая бутылка (bottle_1) — внутри: water`

## Parser forms

- `купить <item_id> у <actor_id>`;
- `buy <item_id> from <actor_id>`;
- `использовать <item_id> на <target_id>`;
- `use <item_id> on <target_id>`.

## Testing

Required:
- sale metadata visible in WorldView;
- TAKE offered bottle fails and does not mutate ownership/money;
- BUY insufficient funds fails atomically;
- BUY wrong/absent seller fails;
- BUY success conserves money between player and NPC and transfers ownership;
- duplicate external BUY cannot double-charge;
- USE without ownership/target fails;
- successful USE fills bottle;
- repeated USE fails without further mutation;
- `/me` shows coins/fill state;
- restart preserves balances and bottle fill;
- parser/Discord application route BUY/USE through canonical GameService.

## Definition of Done

The slice is complete when a player can see Oren's bottle offer, cannot TAKE it for free, can BUY it for 3 of the starting 10 coins, can USE it on the well to produce a persistent filled-bottle state, all transfers are atomic/idempotent, Oren receives the money, `/me` exposes the resulting state, restart preserves it, and all previous multiplayer/consequence tests remain green.
