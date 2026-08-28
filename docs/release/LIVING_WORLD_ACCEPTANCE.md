# Living World v1 acceptance gate

This gate is intentionally independent of the production implementation. It checks the product invariants defined by `docs/superpowers/specs/2026-08-27-living-world-runtime-design.md` through public game/API behavior plus the mandated persistent SQLite model.

## One-command gate

```bash
python scripts/smoke_living_world_acceptance.py
```

The command runs the complete Python test suite and then the existing vertical-slice smoke script. It prints `PASS` only when both gates succeed and returns a non-zero exit code on the first failure.

## Living World acceptance coverage

`tests/test_living_world_acceptance.py` verifies:

- clean runtime/bootstrap state and exactly one real `driftwood_1`;
- Mira depletion -> exactly one request -> Kaspar graph traversal -> real collection -> delivery -> schedule restoration;
- no resource fabrication when driftwood is absent;
- `WAIT 9` equivalence with nine `WAIT 1` actions;
- SQLite restart persistence after collection;
- schedule override arbitration and forced schedule restoration;
- player/autonomous event isolation;
- old `/api/action` requests without modifiers;
- valid WAIT boundaries and invalid type/range payloads without simulation mutation;
- SQLite integrity, foreign keys, duplicate rows/resources/requests and final NPC positions;
- repeated WAIT external-id idempotency;
- player TAKE versus Kaspar collection ordering without resource duplication.

The pre-existing vertical-slice acceptance and smoke suites remain part of the same gate and continue to own the Oren 5-firewood exact-once regression contract.

## Merge rule

Do not weaken a failing acceptance invariant to make the branch green. A failing invariant is a production defect or an integration defect until proven otherwise.
