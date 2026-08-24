# Sam-Sebe-RPG — Playable Vertical Slice

**Sam-Sebe-RPG / Emergent RPG / Living World** is a persistent RPG prototype where the Python game core and SQLite database are authoritative. The browser and LLM are adapters: they can request or propose actions, but only deterministic Python logic changes canonical world state.

## Current vertical slice

The playable route is intentionally small:

`village -> tavern -> Oren -> bring 5 firewood -> deterministic turn-in -> reward/trust/memory -> changed dialogue -> restart persistence`

Implemented now:

- canonical SQLite village state and restart persistence;
- deterministic `LOOK`, `MOVE`, `TAKE`, `DROP` through `GameService`;
- append-only action evidence and idempotent external interactions;
- real-time Clock abstraction and lazy NPC schedule catch-up;
- tavern interior and Oren as the innkeeper;
- five canonical firewood entities;
- one persistent quest: `bring_5_firewood`;
- exact-once quest reward and Oren -> player trust change;
- persistent NPC memory of the completed quest;
- state-aware Oren dialogue with a constrained OpenAI Responses adapter;
- deterministic Russian fallback dialogue when OpenAI is unavailable;
- FastAPI local adapter;
- Phaser 3 + TypeScript browser client with village/tavern scenes, movement, interactions, HUD and dialogue UI.

## Architecture

```text
Phaser / TypeScript browser client
             |
             | JSON HTTP
             v
        FastAPI adapter
          /        \
         v          v
  GameService   DialogueService
  QuestService        |
         \            | read-only context
          \           /
           v         v
          canonical SQLite
```

**Invariant:** browser code and LLM output never write SQLite directly.

## Requirements

- Python 3.12+
- Node.js 20+
- npm
- optional: `OPENAI_API_KEY` for generated Oren dialogue

The critical route remains playable without an OpenAI key; deterministic fallback dialogue is used instead.

## Install — Windows

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Install the browser client:

```powershell
cd web
npm install
cd ..
```

## Run

Terminal 1 — canonical game server:

```powershell
.\.venv\Scripts\python.exe -m samseberpg.server
```

Server: `http://127.0.0.1:8000`

Terminal 2 — browser client:

```powershell
cd web
npm run dev
```

Open the URL printed by Vite (normally `http://127.0.0.1:5173`). Vite proxies `/api` to the Python server.

### Optional OpenAI dialogue

PowerShell:

```powershell
$env:OPENAI_API_KEY="YOUR_KEY"
$env:OPENAI_MODEL="gpt-5"
.\.venv\Scripts\python.exe -m samseberpg.server
```

Do not put API keys in the repository.

## Controls

- `WASD` or arrow keys — move;
- `E` — interact with the nearest highlighted object/NPC/door;
- dialogue buttons — accept or turn in the firewood quest.

## Acceptance route

A clean vertical-slice check is:

1. Start the Python server and browser client.
2. Enter the start village and move the player.
3. Walk to the tavern entrance and press `E`.
4. Approach Oren and press `E`.
5. Accept his request for five pieces of firewood.
6. Leave the tavern and return to the village/workshop area.
7. Collect four firewood pieces.
8. Return to Oren and try to turn in: the server must reject the attempt.
9. Return outside and collect the fifth firewood piece.
10. Return to Oren and turn in successfully.
11. Confirm the quest becomes completed and coins/trust change once.
12. Speak to Oren again: his response must reflect the completed event/memory.
13. Stop both processes completely.
14. Start them again against the same `data/world.sqlite3`.
15. Confirm completed quest, reward/trust and Oren memory are still present.
16. Repeat with `OPENAI_API_KEY` unset: the route must still be completable through fallback dialogue.

## Automated verification

Python/kernel/quest/API/restart acceptance:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Frontend production build:

```powershell
cd web
npm run build
```

The acceptance test is `tests/test_vertical_slice_acceptance.py`.

## Source map

- `src/samseberpg/db.py` — canonical schema/bootstrap;
- `src/samseberpg/game.py` — authoritative generic world actions;
- `src/samseberpg/quest.py` — deterministic firewood quest lifecycle;
- `src/samseberpg/dialogue.py` — Oren context, provider boundary and fallback;
- `src/samseberpg/api.py` — HTTP adapter;
- `src/samseberpg/server.py` — local service wiring;
- `web/src/scenes/` — graphical village/tavern scenes;
- `web/src/ui/DialoguePanel.ts` — dialogue and quest interaction UI;
- `tests/test_vertical_slice_acceptance.py` — end-to-end restart proof.

## Deferred until after this slice

Morning newspaper, procedural quests, autonomous off-screen agents, multiple settlements/biomes, cloud persistence and larger simulation systems are deliberately outside P0.
