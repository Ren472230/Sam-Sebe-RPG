# Sam-Sebe-RPG – Living World Vertical Slice

**Sam-Sebe-RPG / Emergent RPG / Living World** is a playable browser vertical slice about a small persistent village where NPCs have schedules, needs, memories, relationships and causally limited knowledge.

The current candidate combines a deterministic authoritative world with **Living World**, **Living NPC**, **Social World** and **Living Conversation** layers. The goal of this repository is to prove a compact world that keeps living, remembers what happened and gives the player room to intervene.

## What is playable now

- browser game built with Phaser;
- Python/FastAPI authoritative backend;
- persistent SQLite world state;
- player movement, interaction, TAKE / GIVE / WAIT actions and reload persistence;
- Oren's playable firewood quest with reward and saved completion;
- Mira and Kaspar's autonomous resource situation;
- causal NPC-to-NPC knowledge transfer with provenance instead of telepathy;
- Talen's arrival with road news and Oren's bread request;
- free-text NPC dialogue with deterministic offline fallback;
- pair-scoped conversational memory, relationship-aware behavior and grounded NPC initiative from Living Conversation;
- stream presentation mode for a reproducible public demo;
- responsive game shell, including a tested 390 px viewport;
- one-click Markdown export of the current human playtest report.

### Visual status

The current checked-in production art manifest is partial. Approved production Village layers are already integrated, while the runtime keeps the coherent prototype scene until all required layers for a scene are ready. When a production scene becomes complete it receives priority automatically, while missing individual production sprites can safely use their prototype versions.

This keeps the playable candidate visually coherent without claiming unfinished art as final production art.

## Quick start on Windows

### Requirements

- Python 3.12+
- Node.js 22+

Install dependencies from the repository root:

```powershell
python -m pip install -e ".[dev]"
cd web
npm install
cd ..
```

### Human playtest

After dependencies are installed, double-click:

`PLAY_SAM_SEBE_RPG.bat`

The launcher resets only the isolated Stream Slice database, runs the existing preflight, waits for the local web server, and opens the normal player-facing game at:

`http://127.0.0.1:5173/`

Play naturally. At the end, press **Скачать отчёт теста** in the game and share the downloaded `.md` file for analysis.

### Reproducible public demo

For a clean reproducible audience-oriented demo:

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_STREAM_SLICE.ps1 -Reset
```

The launcher runs the Stream Slice preflight before starting the game. Then open:

`http://127.0.0.1:5173/?stream=1`

To continue the same saved Stream Slice state later:

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_STREAM_SLICE.ps1
```

`-Reset` only resets the isolated Stream Slice database used for the demo.

## OpenAI is optional

The game can run without `OPENAI_API_KEY`. NPC dialogue then uses deterministic grounded fallback replies, while world state, memory, knowledge propagation and gameplay remain authoritative on the server.

If a live OpenAI provider is configured, it generates language plus narrowly validated conversational metadata. It does not receive authority to mutate physical world state or turn player claims into objective world facts.

## A short demo route

A useful first demonstration is:

1. start the clean Stream Slice;
2. move around the village and observe NPC schedules and the world pulse;
3. talk to Mira when her workshop needs useful wood;
4. let Kaspar act on his own or intervene by taking and delivering the resource yourself;
5. reach the tavern after Talen arrives with news from the eastern road;
6. talk to Talen and Oren and complete the bread help loop;
7. reload the page and verify that world and social state persist.

The complete reproducible runbook is in `docs/release/STREAM_SLICE_V1.md`.

## Controls and interaction

- `WASD` – movement in the active scene;
- `E` – contextual interaction in the main quest route;
- on-screen Living World controls – travel, wait, talk, take and give where the current world state allows it;
- `?stream=1` – audience-oriented presentation mode.

## Architecture

```text
Browser / Phaser
       |
       v
 FastAPI game API
       |
       v
 authoritative services
  |      |       |
  v      v       v
world  dialogue  social knowledge
        |
        v
      SQLite
```

Key boundary: SQLite + deterministic Python services own canonical facts, inventory, locations, relations and physical side effects. Language-model output stays bounded to dialogue and validated conversational metadata.

## Verification

The playable candidate is continuously checked through independent GitHub Actions gates covering:

- full Python test suite;
- Stream Slice focused tests and preflight;
- SQLite integrity and reopen persistence;
- web contract tests;
- production TypeScript/Vite build;
- Chromium end-to-end gameplay;
- Living NPC, Social World and Stream Slice browser acceptance;
- Windows compatibility and backend boot.

Current autonomous validation evidence is tracked in draft PR #47. `main` remains the protected control until a separate integration decision is made.

## Repository map

- `src/samseberpg/` – authoritative game, world, dialogue, memory and social systems;
- `web/` – Phaser browser client and browser acceptance tests;
- `scripts/` – launchers, preflight, reset and smoke checks;
- `PLAY_SAM_SEBE_RPG.bat` – one-click clean human playtest launcher for Windows;
- `RUN_STREAM_SLICE.ps1` – Windows demo launcher;
- `docs/release/STREAM_SLICE_V1.md` – detailed demo runbook;
- `docs/superpowers/` – approved design and implementation plans;
- `tests/` – backend, persistence, Living World and conversation acceptance tests.

## Current product boundary

This repository currently represents a **playable, persistent vertical slice**, not a content-complete RPG. It proves the core experience of a small causally connected living village. More locations, progression, combat, crafting, broader content and final production art remain future product work.
