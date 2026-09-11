# Sam-Sebe-RPG – Living World Vertical Slice

**Sam-Sebe-RPG / Emergent RPG / Living World** is a playable browser vertical slice about a small persistent village where NPCs have schedules, needs, memories, relationships and causally limited knowledge.

The current integration candidate combines a deterministic authoritative world with **Living World**, **Living NPC**, **Social World**, **Living Conversation** and a temporary complete SVG stream visual pack. The goal of this repository is to prove a compact world that keeps living, remembers what happened and gives the player room to intervene.

## Current integration candidate

- PR: **#49 – Integration: world-ready candidate + stream SVG pack**
- branch: `integration/world-ready-svg-v1`
- exact candidate HEAD: `7d7ec138cb15c253f22435f8d5c2983a2e1d1cd8`
- base `main`: `813ac7beb233645546fcc1e7bda3827efe63dcdc`
- state: **OPEN / DRAFT / UNMERGED**
- release/reproducibility work branch: `agent/release-reproducibility-v1`

At that exact candidate HEAD, Prototype Web CI, Windows Compatibility and Visual Forge passed. The backend, dependency installation, web contract and production-build stages in the browser-bearing gates also passed. Playable Candidate, Living World Integration and Stream Slice still have browser acceptance failures and are awaiting the parallel E2E stabilization work. No future browser PASS is claimed here.

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

`web/public/assets/production/manifest.json` is currently version 2 with `status: "ready"`. The checked-in runtime uses a **temporary complete all-SVG Stream Slice pack** with the locked Start Village palette: six Village layers, two Tavern layers, player/Oren character SVGs, the firewood prop and dialogue frame are materialized.

This pack is suitable for the current playable/integration candidate and automated checks. It is still temporary production-facing art rather than the final art pass. Prototype assets remain available as runtime fallback paths where the existing asset policy requires them.

## Reproducible dependency policy

The repository now has two explicit dependency snapshots for release work:

- `web/package-lock.json` (`lockfileVersion: 3`) is the committed npm dependency lock. CI uses `npm ci` so package resolution must match it exactly.
- `constraints/python-3.12.txt` snapshots the Python 3.12 runtime/test dependency set used by release CI and the Windows launcher. `pyproject.toml` keeps lower-bound package metadata so the project is still installable as a normal Python package.

CI stays on the Python 3.12 and Node.js 22 runtime families. Exact runtime patch versions and the isolated `setuptools>=75` build backend are intentionally not hard-locked yet; see `docs/release/REPRODUCIBILITY_AUDIT.md` for the remaining reproducibility boundary.

## Quick start on Windows

### Requirements

- Python 3.12+
- Node.js 22+ with npm

### Human playtest

On a freshly downloaded ZIP, double-click:

`PLAY_SAM_SEBE_RPG.bat`

The launcher bootstraps missing local project dependencies automatically. Python installation uses `constraints/python-3.12.txt`. When `web/package-lock.json` is present, web installation uses `npm ci`; the launcher falls back to `npm install` only for a local checkout that is missing the lockfile. It then resets only the isolated Stream Slice database, runs the existing preflight, waits for the local web server, and opens the normal player-facing game at:

`http://127.0.0.1:5173/`

If startup fails, the `Sam-Sebe-RPG server` PowerShell window stays open so the actual error remains readable instead of disappearing.

If `OPENAI_API_KEY` is not already present in the process, the playtest launcher asks for it using hidden PowerShell input. The key is kept only in that process and is not written to the repository.

Play naturally. At the end, press **Скачать отчёт теста** in the game and share the downloaded `.md` file for analysis.

Manual deterministic dependency installation remains available for development/debugging:

```powershell
python -m pip install -c constraints/python-3.12.txt -e ".[dev]"
cd web
npm ci --no-audit --no-fund
cd ..
```

### Reproducible public demo

For a clean audience-oriented demo:

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

The candidate is checked through independent GitHub Actions gates covering Python tests, Stream Slice preflight, SQLite persistence, web contracts, production build, Chromium gameplay, Living NPC/Social World/Stream Slice browser acceptance and Windows compatibility.

Evidence for exact candidate HEAD `7d7ec138cb15c253f22435f8d5c2983a2e1d1cd8`:

| Gate | Run | Current result |
| --- | ---: | --- |
| Prototype Web CI | `34473124187` | PASS |
| Windows Compatibility Gate | `34473124237` | PASS |
| Visual Forge Gate | `34473124446` | PASS |
| Playable Candidate Gate | `34473124248` | FAIL at browser integrated route; backend/install/contracts/build passed |
| Living World Integration Gate | `34473124220` | FAIL at real-browser critical route; dependency/build stages passed |
| Stream Slice Gate | `34473124246` | FAIL at Chromium acceptance; Python/preflight/install/contracts/build passed |

The release branch also has `.github/workflows/release-reproducibility.yml`, a cross-platform clean-checkout gate that validates constrained Python installation, `npm ci`, the full Python suite, Stream Slice preflight, web contracts, production build, Playwright package resolution and a Windows backend boot without changing browser-game test semantics.

The current release blocker is **browser E2E stabilization**. PR #49 remains draft and unmerged. No GitHub Release has been published for this candidate.

## Repository map

- `src/samseberpg/` – authoritative game, world, dialogue, memory and social systems;
- `web/` – Phaser browser client, `package-lock.json` and browser acceptance tests;
- `constraints/python-3.12.txt` – reproducible Python 3.12 dependency snapshot for release CI/launcher;
- `scripts/` – launchers, preflight, reset and smoke checks;
- `PLAY_SAM_SEBE_RPG.bat` – one-click clean human playtest launcher for Windows;
- `RUN_STREAM_SLICE.ps1` – Windows demo launcher;
- `docs/release/STREAM_SLICE_V1.md` – detailed demo runbook;
- `docs/release/REPRODUCIBILITY_AUDIT.md` – dependency/repository/CI reproducibility audit;
- `docs/superpowers/` – approved design and implementation plans;
- `tests/` – backend, persistence, Living World and conversation acceptance tests.

## Current product boundary

This repository currently represents a **playable, persistent vertical slice**, not a content-complete RPG. It proves the core experience of a small causally connected living village. More locations, progression, combat, crafting, broader content and final production art remain future product work.
