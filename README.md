# Sam-Sebe-RPG — Shared World Kernel

A deliberately small multiplayer-first kernel for **Emergent RPG / Living World / Сам-себе-RPG**.

The current milestone proves that 2–5 players can inhabit one canonical SQLite village, mutate shared state atomically, survive retries/restarts, and lazily synchronize deterministic NPC schedules to real time.

## Implemented scope

- one shared village with three locations;
- three scheduled NPCs and twelve entities;
- Discord user ID → persistent player actor mapping;
- shared observation;
- deterministic `LOOK`, `MOVE`, `TAKE`, `DROP`;
- one SQLite write transaction per gameplay action;
- append-only `ActionEvent` evidence for successes and gameplay failures;
- idempotency by external interaction ID;
- restart persistence;
- `SystemClock` / `FakeClock`;
- lazy NPC schedule catch-up;
- serialized concurrent mutations with `BEGIN IMMEDIATE`;
- no Discord SDK or LLM dependency in the core.

Deferred: Discord adapter/UI, LLM parsing, voice, combat, crafting, progression, large-world generation, Redis/PostgreSQL/microservices.

## Requirements

- Python 3.12+
- pytest for development/testing

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
python -m pip install -e ".[dev]"
```

## Tests

```bash
pytest -q
```

Concurrency proof:

```bash
pytest -q tests/test_concurrency.py
```

## Executable multiplayer proof

After installing the package:

```bash
python scripts/demo_shared_world.py
```

The demo creates a clean temporary SQLite database and proves:

1. Player A and Player B both see `stone_flat_1`.
2. Player A takes it.
3. Player B immediately stops seeing it.
4. Reopening the database preserves Player A's ownership.
5. `FakeClock` advances from 08:00 to 20:00 UTC.
6. The next world touch lazily moves Mira to `village_square` with her evening activity.

## Architecture

```text
adapter / tests / future Discord
            |
            v
     CanonicalAction
            |
            v
       GameService
         /      \
        v        v
WorldSynchronizer  deterministic rules
        \        /
         v      v
        SQLite
 state + ActionEvent + idempotency
```

SQLite is authoritative. LLMs and Discord adapters are not allowed to write canonical state directly.

## Source map

- `src/samseberpg/domain.py` — typed actions/results/views
- `src/samseberpg/clock.py` — replaceable world clock
- `src/samseberpg/db.py` — schema, connection policy, village bootstrap
- `src/samseberpg/world.py` — deterministic lazy NPC catch-up
- `src/samseberpg/game.py` — player registration, observation, authoritative actions
- `tests/` — persistence, shared state, idempotency, time and concurrency proofs
- `scripts/demo_shared_world.py` — clean end-to-end proof

## Next slice

Only after this kernel stays green should development move to the Discord gameplay adapter (`/look`, `/me`, `/act`) while keeping the simulation package independent of Discord and LLM SDKs.
