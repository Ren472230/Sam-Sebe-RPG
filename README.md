# Sam-Sebe-RPG — Playable Vertical Slice

A small persistent Living World prototype with a graphical Phaser client, deterministic Python game logic, canonical SQLite state and an LLM dialogue layer that is not allowed to mutate world truth directly.

## Current vertical slice

The current P0 proves one complete playable causal loop:

`village -> tavern -> Oren -> accept 5-firewood quest -> collect real canonical items -> deterministic turn-in -> reward/trust/memory -> changed Oren reaction -> reload preserves consequence`

### Implemented

- graphical browser client with Phaser 3 + TypeScript + Vite;
- start village and tavern scenes;
- WASD movement, collision bounds and interaction prompts;
- canonical SQLite world state;
- deterministic `LOOK`, `MOVE`, `TAKE`, `DROP`;
- one authoritative `bring_5_firewood` quest;
- exact-once quest completion and reward;
- persistent Oren -> player trust;
- persistent NPC memory;
- LLM dialogue adapter with constrained proposals only;
- deterministic fallback dialogue, so the critical route remains playable without OpenAI;
- FastAPI adapter between browser and authoritative game services;
- restart/reload persistence;
- append-only action evidence and idempotency;
- real-time lazy NPC schedule catch-up;
- automated real-browser Chromium acceptance of the full critical route.

### Still intentionally deferred from P0

- final production visual assets from MASTER STYLE REFERENCE v1;
- second NPC gameplay loop;
- generalized procedural quest generation;
- full Law of Forgetting ranking/decay;
- morning newspaper/digest;
- autonomous off-screen simulation;
- larger economy, regions and biomes.

## Requirements

- Python 3.12+
- Node.js 22+
- npm

## Backend setup

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m samseberpg.server
```

Backend starts at:

`http://127.0.0.1:8000`

If `OPENAI_API_KEY` is absent, the game automatically uses deterministic dialogue fallback for the critical route.

The default persistent save is:

`data/world.sqlite3`

Override it with `SAM_SEBE_DB` when an isolated database is required.

## Browser client

In a second terminal:

```powershell
cd web
npm install
npm run dev
```

Open the Vite URL, normally:

`http://127.0.0.1:5173`

Controls:

- `WASD` — move;
- `E` — interact;
- dialogue buttons — quest/dialogue actions.

## Critical acceptance route

1. Start in the village.
2. Walk to the tavern and press `E` when prompted.
3. Approach Oren and talk to him.
4. Accept the firewood task.
5. Leave the tavern.
6. Collect four firewood items.
7. Return to Oren and verify early turn-in is rejected.
8. Collect the fifth firewood item.
9. Return and complete the task.
10. Verify HUD shows completed quest, `15` coins and Oren trust `10`.
11. Verify Oren acknowledges that the player helped him.
12. Reload the page and verify the completed consequence and tavern location persist.

## Tests

Python:

```bash
pytest -q
```

Frontend production build:

```bash
cd web
npm install
npm run build
```

Real browser acceptance:

```bash
cd web
npx playwright install chromium
npm run test:e2e
```

The browser acceptance uses an isolated `data/e2e-world.sqlite3` save and captures evidence screenshots for:

- clean village start;
- Oren quest offer;
- completed consequence;
- post-reload persistent state.

## Architecture

```text
Phaser / TypeScript client
          |
          | HTTP
          v
       FastAPI
          |
    +-----+-----------------+
    |                       |
    v                       v
GameService             DialogueService
    |                 read-only context
    |                       |
    +-----------+-----------+
                v
          Canonical SQLite
```

### Authority invariant

SQLite is authoritative. Browser code and LLM output never write world state directly. Every gameplay mutation is validated and committed through deterministic Python application logic.

## Existing kernel guarantees retained

- atomic gameplay writes;
- append-only `ActionEvent` evidence;
- idempotency by external interaction ID;
- restart persistence;
- `SystemClock` / `FakeClock`;
- lazy deterministic NPC schedule catch-up;
- serialized concurrent mutations with `BEGIN IMMEDIATE`.

## Visual status

The current graphical scenes are a functional greybox in the locked project palette. They intentionally prove gameplay/readability before final asset replacement.

Visual R&D is closed. Production replacement must follow MASTER STYLE REFERENCE v1 / VISUAL STYLE BIBLE v1.0 and must not reopen the art direction.

## Primary source map

- `src/samseberpg/db.py` — canonical schema and village bootstrap;
- `src/samseberpg/game.py` — base authoritative actions;
- `src/samseberpg/quest.py` — one deterministic vertical-slice quest;
- `src/samseberpg/dialogue.py` — state-aware LLM/fallback dialogue adapter;
- `src/samseberpg/api.py` — HTTP adapter;
- `src/samseberpg/server.py` — local application entrypoint;
- `web/src/scenes/` — Phaser village/tavern presentation;
- `web/src/ui/DialoguePanel.ts` — DOM dialogue UI;
- `tests/` — Python authoritative-state tests;
- `web/tests/vertical-slice.spec.ts` — real Chromium critical-route acceptance.
