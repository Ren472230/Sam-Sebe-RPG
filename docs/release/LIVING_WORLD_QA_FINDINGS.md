# Living World v1 — independent QA findings

Status is based on the current parallel branches, not developer claims.

## QA-001 — official application composition does not wire LivingWorldService

Owner: DEV-2

Reproduction:
1. Build the application with `samseberpg.server.build_app(db_path)`.
2. Create a player session.
3. POST `/api/action` with `action_type=WAIT` and `modifiers={"ticks":1}`.

Expected:
- HTTP action succeeds;
- Living World advances by one tick;
- one player WAIT action event is recorded.

Actual on `dev/living-world-integration` at `1998c6fa77f552d7cb3c4463889332c748c306c5`:
- `build_app()` constructs `GameService(db, clock)` without a Living World advancer;
- the WAIT path raises `RuntimeError("LivingWorldService is not configured for WAIT actions")`.

Acceptance test: `test_official_build_app_wires_wait`.

## QA-002 — deleted driftwood can be recreated by database bootstrap

Owner: DEV-1

Reproduction:
1. Initialize a database so `driftwood_1` has existed.
2. Delete `driftwood_1`.
3. Re-run `GameDatabase.initialize()`.

Expected:
- `driftwood_1` remains absent because the resource has already existed in this save;
- bootstrap must not act as resource respawn.

Actual on `dev/living-world-core` after runtime persistence was added:
- `driftwood_1` is part of `_ENTITIES`;
- bootstrap uses `INSERT OR IGNORE` against the current `entities` table only;
- after deletion there is no tombstone/history record, so a later initialize inserts the row again.

Acceptance test: `test_missing_resource_never_fabricates_or_repeats_request_and_does_not_respawn`.

## Notes

- DEV-2's own CI became green after commit `1998c6fa77f552d7cb3c4463889332c748c306c5`, but it does not cover QA-001.
- These findings do not authorize production fixes from the QA branch.
- Do not merge this QA branch into `main` until the independent acceptance gate is green on the integrated DEV-1 + DEV-2 state.
