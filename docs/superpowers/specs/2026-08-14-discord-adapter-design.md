# Discord Adapter — Design Specification

## Goal

Put the verified Shared World Kernel behind a minimal Discord slash-command surface so 2–5 players can enter the same village without Discord-specific code entering the simulation layer.

## Approaches considered

1. **discord.py Gateway + slash commands — selected.** Smallest practical local MVP, native `/` UX, no public HTTP endpoint, no Message Content intent, and a mature command tree API.
2. Raw Discord HTTP interactions. Fewer runtime abstractions but requires a publicly reachable HTTPS endpoint and signature handling; unnecessary for the zero-budget local MVP.
3. Prefix/message bot. Easy to prototype but requires reading ordinary messages and couples gameplay input to Message Content.

## Architecture

```text
Discord Interaction
      |
      v
 discord_bot.py          # only module importing discord.py
      |
      v
DiscordGameApplication   # pure/testable adapter service
      |        |
      |        +--> deterministic parser
      |        +--> text presentation
      v
 GameService             # unchanged authoritative core
      |
      v
 SQLite
```

## Commands

### `/look`
Registers/loads the Discord user, observes the world, and returns current location, description, visible actors, and visible entities.

### `/me`
Registers/loads the user and returns current location plus inventory.

### `/act text:<free text>`
This slice uses a deterministic mini-grammar:
- `осмотреться`, `look`;
- `идти <location_id>`, `move <location_id>`;
- `взять <entity_id>`, `take <entity_id>`;
- `положить <entity_id>`, `drop <entity_id>`.

Unknown text returns help and never reaches GameService. Parser output is always a `CanonicalAction`. The Discord interaction ID is passed unchanged as `external_id`.

## Pure application adapter

`DiscordGameApplication` methods:
- `handle_look(discord_user_id: str, display_name: str) -> str`;
- `handle_me(discord_user_id: str, display_name: str) -> str`;
- `handle_act(discord_user_id: str, display_name: str, text: str, interaction_id: str) -> str`.

Every method uses idempotent player registration.

## Runtime configuration

- `DISCORD_BOT_TOKEN` required;
- `DISCORD_GUILD_ID` optional for fast guild command sync;
- `SAM_SEBE_DB` optional, default `game.db`.

No secrets are committed.

## Dependency policy

Core remains standard-library only. Discord is optional: `discord = ["discord.py>=2.7,<3"]`. Only `discord_bot.py` may import `discord`.

## Error handling

Parser misses are ordinary help responses and create no action event. Gameplay failures render deterministic `ActionResult` feedback. Unexpected callback errors are logged and returned to Discord as generic ephemeral errors.

## Testing

Local tests do not require Discord/network. They cover parser forms, `/look`, `/me`, `/act`, idempotency, unknown-input no-event behavior, bounded rendering, and Discord import isolation. Gateway connectivity is not testable here without a token/network runtime.

## Definition of Done

Optional discord.py dependency is declared; pure adapter tests pass; the runtime exposes `/look`, `/me`, `/act`; secrets stay in environment variables; existing kernel tests remain green; compileall and import-isolation checks pass; README contains founder setup/run steps.
