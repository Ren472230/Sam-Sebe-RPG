# Sam-Sebe-RPG Standalone HTML v1 – Design

Status: approved in chat as an isolated autonomous experiment; written specification requires the standard review gate before implementation  
Branch: `experiment/standalone-html-v1`  
Base: `88d526d84d500231f4c8219a71214e6da2999329`  
Source gameplay line: `agent/autonomy-pilot-v0.1` / PR #55, derived from PR #53  
Reference one-file prototype: user-provided `mini-game-starter(1).html`

## 1. Product goal

Prove that the current Sam-Sebe-RPG vertical slice can become a genuinely playable, portable one-file game without destroying the existing project architecture.

The first result must be a single file:

`standalone/dist/sam-sebe-rpg.html`

A player must be able to copy that file to another computer, open it locally in a modern browser and play without running Python, FastAPI, SQLite, npm, a local server or any external account.

The experiment is successful if the one-file version preserves the recognizable product fantasy of the existing project: a small living village, visible world progression, persistent consequences, distinct NPC state and a short causal sequence that the player can influence.

This experiment does not replace the existing server-backed candidate. Until a separate owner decision, the server-backed project remains the authoritative production line and the standalone file is an isolated product experiment.

## 2. Chosen approach

Use a hybrid development architecture:

1. source code remains split into small modules under `standalone/src/`;
2. tests run against those modules before packaging;
3. a deterministic build script in `standalone/scripts/` assembles all JavaScript, CSS and SVG assets into one HTML file;
4. the shipped artifact has no runtime dependency on repository files or network resources.

Do not hand-maintain one giant HTML source file.

This preserves maintainability while delivering the one-file experience the user wants.

## 3. Relationship to the current game

The current browser game uses Phaser, FastAPI and SQLite, with Python services owning authoritative world state. The standalone experiment cannot preserve that exact runtime boundary while also opening directly from a local HTML file without a server.

Therefore v1 uses an explicit compatibility boundary:

- existing project mechanics and current Stream Slice behavior are the design reference;
- the standalone file contains a deterministic JavaScript simulation that implements only the approved portable slice;
- standalone state is never written back into the server-backed SQLite world;
- standalone saves are tagged with a separate game identifier and schema version;
- no claim is made that a standalone save can be imported into the server-backed game.

The standalone experiment must preserve causal rules, deterministic progression and visible consequences where those mechanics are ported.

## 4. Scope of the first playable slice

The first complete slice contains:

### Locations

- Start Village;
- Tavern interior.

### Characters

- player;
- Oren;
- Mira;
- Kaspar;
- Talen.

### Core player verbs

- move in the current scene;
- interact with a nearby NPC or object;
- talk;
- take;
- give;
- wait 1 world step;
- wait 5 world steps;
- enter or leave the tavern.

### Core progression

- Oren can start the existing firewood task;
- player can collect the required firewood and return it;
- reward and completed state persist;
- world time advances through player actions and explicit waiting;
- Talen arrives at the configured world step;
- Talen carries the eastern-road information;
- Oren can learn that information through the grounded arrival/contact route;
- unrelated NPCs do not receive the information automatically.

### Supporting living-world behavior

- Mira has a visible workshop concern;
- Kaspar has a small deterministic activity state;
- NPC status can change when world steps advance;
- the world pulse shows recent meaningful events;
- the event journal records important state changes.

The full Living Conversation v2 provider path is outside v1. Dialogue is deterministic and state-aware so that the file remains fully offline.

## 5. Explicit exclusions from v1

Do not include in the first implementation:

- network calls;
- external language-model providers;
- API keys;
- server synchronization;
- SQLite in the browser;
- complete parity with every backend table or service;
- procedural content generation;
- large new quest lines;
- final production art;
- multiplayer;
- account authentication;
- cloud saves;
- conversion of existing server saves.

The experiment should prove the product format before expanding content.

## 6. Runtime architecture

Create the following source boundaries.

### `standalone/src/domain/state.js`

Owns serializable game state and schema defaults.

Target state shape:

```text
StandaloneState
├─ schemaVersion
├─ rngSeed
├─ world
│  ├─ tick
│  ├─ phase
│  └─ recentEvents
├─ player
│  ├─ scene
│  ├─ x / y
│  ├─ inventory
│  ├─ coins
│  └─ quest
├─ actors
│  ├─ oren
│  ├─ mira
│  ├─ kaspar
│  └─ talen
├─ knowledge
├─ relationships
├─ dialogueMemory
├─ stats
└─ meta
```

Only plain serializable values are stored. No DOM, rendering or browser object belongs in simulation state.

### `standalone/src/domain/reducer.js`

Owns deterministic game actions.

Expected action families:

- `MOVE_PLAYER`;
- `INTERACT`;
- `TALK`;
- `TAKE`;
- `GIVE`;
- `WAIT`;
- `ENTER_TAVERN`;
- `LEAVE_TAVERN`.

Each accepted action returns:

- new state;
- structured events;
- optional player-facing message.

The reducer must never depend on rendering timing.

### `standalone/src/domain/world.js`

Advances world steps and applies deterministic NPC/world rules.

Responsibilities:

- Talen arrival;
- Oren hospitality/contact beat;
- Mira and Kaspar small activity transitions;
- causal knowledge transfer;
- event generation;
- idempotency of one-time beats.

### `standalone/src/domain/dialogue.js`

Provides offline state-aware dialogue.

Dialogue chooses deterministic response variants from:

- NPC identity;
- current world state;
- NPC knowledge;
- quest state;
- recent pair interaction;
- relationship mode.

It must avoid inventing objective facts and must preserve the existing knowledge boundaries.

### `standalone/src/save/save-store.js`

Port the useful persistence capabilities from the one-file prototype:

- 3 independent save slots;
- autosave after every accepted action;
- latest-known-good backup per slot;
- schema version;
- import/export JSON;
- damaged-primary recovery from backup;
- explicit reset.

Use a standalone namespace so it cannot collide with other prototypes.

### `standalone/src/view/world-view.js`

Owns visual presentation of the current location.

V1 uses an SVG-first renderer inside the HTML document rather than Phaser. This keeps the artifact small, offline and easy to inline.

Responsibilities:

- scene background/layers;
- player position;
- NPC position/status;
- interactable objects;
- interaction hint;
- simple transitions between village and tavern.

### `standalone/src/input/input-map.js`

Maps physical input to game intents in one place.

Required controls:

- WASD / arrow movement;
- `E` interaction;
- Escape closes dialogue/menu;
- mouse/touch fallback for primary interactions.

Text input, open dialogue and menus must block movement exactly as modal states.

### `standalone/src/ui/`

DOM-based interface for:

- objective;
- inventory;
- world pulse;
- dialogue;
- save slots;
- journal;
- settings/help;
- developer panel.

The playfield stays visually primary.

### `standalone/src/debug/dev-tools.js`

Hidden developer tools should preserve the useful ideas from the prototype:

- inspect/copy current state;
- add test resources;
- advance world steps;
- run deterministic simulations without modifying the active slot;
- show seed and current tick;
- reset current slot.

## 7. Visual direction

Use the established project palette lock:

- 55–60% milk / marble white;
- 20–25% graphite / near black;
- 5–7% scarlet plus black cultural accent;
- 3–5% bright sky turquoise;
- 2–3% warm amber / old gold;
- green and brown remain strongly muted support colors.

V1 should reuse or adapt the existing temporary SVG Stream Slice assets where practical.

The visual objective is a readable 2.5D cardboard-theatre village rather than a generic dashboard.

The one-file prototype contributes save/debug/interface infrastructure ideas, not the final visual identity.

## 8. Asset policy

The build must ship with every required visual asset embedded.

Preferred order:

1. existing checked-in SVG production assets from the Stream Slice pack;
2. small additional SVG authored specifically for standalone interaction markers or HUD symbols;
3. CSS shapes only for trivial decoration.

Do not add remote fonts, remote images, CDN libraries or external scripts.

The final HTML must still render correctly with the network disabled.

## 9. Build architecture

Create a deterministic Node build script with no hidden runtime services.

Target flow:

```text
standalone/src modules
        +
standalone/assets SVG
        +
standalone/styles
        ↓
standalone/scripts/build.mjs
        ↓
standalone/dist/sam-sebe-rpg.html
```

The builder must:

- bundle or concatenate the approved JavaScript modules in a deterministic order;
- inline CSS;
- inline SVG assets;
- escape embedded data safely;
- inject game version and save schema version;
- fail if a required asset is missing;
- produce exactly one distributable HTML artifact.

The source modules remain the maintained implementation. The generated HTML is treated as a build artifact.

## 10. Save format

Use the proven envelope pattern from the user-provided prototype.

Required envelope fields:

- `format`;
- `schemaVersion`;
- `gameId`;
- `gameVersion`;
- `slotId`;
- `savedAt`;
- `state`.

Target `gameId`:

`sam-sebe-rpg-standalone`

V1 must include migration infrastructure even if the migration map is initially empty.

## 11. Determinism

Use seeded pseudo-random behavior only.

Rules:

- every random gameplay choice consumes and stores the next seed;
- save/reload preserves the seed;
- simulations clone source state and do not mutate the live slot;
- the same state plus action produces the same resulting game state;
- visual animation may be nondeterministic, but it cannot affect simulation outcomes.

## 12. Causal knowledge model

Standalone v1 keeps a narrow knowledge store.

Each durable fact record should include:

- fact key;
- actor who knows it;
- source actor or event;
- learned tick.

For the Talen route:

1. Talen arrives with eastern-road knowledge;
2. Talen is physically available in the tavern;
3. a grounded contact/hospitality beat can transfer the fact to Oren;
4. Mira and Kaspar remain unaware unless a future explicit route transfers it.

This is a minimal portable preservation of the Social World causal rule.

## 13. Player experience flow

A fresh slot should support this readable sequence:

1. open the file;
2. see Start Village immediately;
3. learn movement and interaction from a compact hint;
4. find the tavern and speak with Oren;
5. accept the firewood request;
6. collect and return firewood;
7. receive reward and see the world pulse change;
8. wait or continue acting until Talen arrives;
9. enter the tavern and see the new visitor;
10. talk/interact and observe the road-news consequence;
11. reload the HTML and confirm that progress remains;
12. optionally export the save.

The first useful play session target is approximately 10–20 minutes.

## 14. Error handling

The standalone file must fail visibly and recoverably.

Required behavior:

- corrupted primary save attempts backup recovery;
- corrupt import is rejected with a readable message;
- unsupported newer schema is rejected;
- missing optional visual element falls back to a simple local placeholder;
- missing required build-time asset fails the build;
- runtime exception is recorded in a local diagnostic log and surfaced in a compact error notice.

No error path may silently destroy a valid save.

## 15. Test strategy

Implementation follows red-to-green development.

### Domain tests

Cover:

- fresh state;
- firewood quest start/completion;
- TAKE/GIVE validity;
- WAIT progression;
- Talen arrival exactly once;
- causal road fact transfer;
- knowledge isolation;
- save/reload determinism;
- seeded simulation repeatability.

### Save tests

Cover:

- slot isolation;
- autosave envelope;
- backup recovery;
- invalid JSON import;
- wrong game identifier;
- future schema rejection;
- migration hook behavior.

### Build tests

Cover:

- final file exists;
- final file contains no remote script/style/image dependency;
- required SVG markers are embedded;
- no unresolved source file path remains in shipped HTML;
- output can be opened through `file://`.

### Browser acceptance

A local browser test must verify the complete v1 sequence from new game through Oren, firewood, world advancement, Talen and persistence.

The standalone acceptance suite is separate from the seven mandatory gates of the server-backed integration candidate.

## 16. Repository isolation

All v1 implementation lives under `standalone/` plus its design/plan/test documentation.

Do not modify the existing Python/FastAPI/SQLite gameplay implementation merely to make the standalone experiment easier.

Do not merge this experiment into `main`, PR #53 or PR #55 without a separate owner decision.

If a reusable defect fix is discovered in the current canonical game while porting behavior, record it separately rather than silently changing both lines at once.

## 17. Success criteria

Standalone HTML v1 is technically successful when one exact commit proves all of the following:

- `standalone/dist/sam-sebe-rpg.html` is produced;
- opening the file locally requires no server;
- the file uses no runtime network dependency;
- new game works;
- player movement and interaction work;
- village and tavern are reachable;
- Oren firewood loop works;
- world-step progression works;
- Talen arrival and causal road-news transfer work;
- save slots persist progress;
- backup recovery works;
- export/import works;
- reload preserves the same world state;
- automated domain/save/build tests pass;
- browser acceptance passes on the exact same commit.

A later human experience check decides whether this format should become the primary client direction.

## 18. Rollout after v1

Only after v1 is proven should the owner choose among:

1. keep standalone as a fast prototype/demo distribution;
2. evolve standalone into the primary playable client while the server project remains the richer simulation laboratory;
3. use the experiment only to extract better save/build/test patterns back into the existing client.

No choice is made automatically by the v1 experiment.
