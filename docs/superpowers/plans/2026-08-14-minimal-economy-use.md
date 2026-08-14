# Minimal Economy + USE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add one deterministic purchase and one deterministic item-use loop without expanding into a general economy/crafting engine.

**Architecture:** Keep all validation and money/item mutation in the existing `GameService.execute()` transaction. Sale/use affordances are canonical entity state interpreted by whitelisted deterministic rules. No new service or dependency.

**Tech Stack:** Existing Python/sqlite3/pytest project.

## Constraints

- Currency must be conserved on BUY.
- TAKE cannot bypass a sale.
- USE has one whitelisted fill-container rule only.
- No SELL, jobs, dynamic pricing, hunger or crafting.
- Existing external-id idempotency protects BUY/USE unchanged.

### Task 1: Economy state and visibility

- Modify `src/samseberpg/domain.py`, `db.py`, `game.py`.
- [ ] RED tests: WorldView exposes starting 10 coins; bottle offer has price/seller/fillable state; Oren has canonical coin balance.
- [ ] Add `coins` to `npcs`; bootstrap Oren balance and bottle/well affordance state.
- [ ] Add player `coins` to WorldView observation.
- [ ] GREEN full suite.

### Task 2: Protect sale items from TAKE

- Modify `game.py`; test `tests/test_economy_use.py`.
- [ ] RED test: TAKE bottle returns `FOR_SALE_ONLY`, no ownership/money mutation.
- [ ] Implement sale check in TAKE before transfer.
- [ ] GREEN full suite.

### Task 3: BUY atomic transfer

- Add `ActionType.BUY`; modify `game.py`.
- [ ] RED tests for wrong seller, absent seller, insufficient funds, success and exact evidence.
- [ ] Implement BUY: validate item/seller/location/price/funds, debit player, credit NPC, transfer item.
- [ ] RED/GREEN idempotency test proving same external ID charges once.
- [ ] GREEN full suite.

### Task 4: USE fill-container affordance

- Add `ActionType.USE`; modify `game.py`.
- [ ] RED tests for unowned item, absent/unsupported target, success and repeat.
- [ ] Implement owned fillable container + local water source -> `filled_with=water`.
- [ ] Persist exact before/after evidence.
- [ ] GREEN full suite.

### Task 5: Parser and presentation

- Modify `parser.py`, `presentation.py`, parser/Discord tests.
- [ ] RED parser tests for RU/EN BUY/USE.
- [ ] RED rendering tests for sale price, `/me` coins and filled state.
- [ ] Implement grammar/rendering.
- [ ] Prove Discord application BUY/USE reaches GameService and remains retry-safe.

### Task 6: Persistence demo and verification

- Create `scripts/demo_economy_use.py`; update README.
- [ ] Demo starts at 10 coins, BUY bottle for 3, confirms Oren receives 3, USE at well, restart sees 7 coins and filled bottle.
- [ ] Run compileall, full pytest and all demos.
- [ ] Re-run concurrency/idempotency regressions.
