# Discord Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a minimal slash-command Discord surface over the existing shared-world kernel without coupling Discord to simulation.

**Architecture:** Pure parser/presentation/application modules are tested without Discord. Only `discord_bot.py` imports discord.py and converts interactions into calls to `DiscordGameApplication`.

**Tech Stack:** Python 3.12+, existing kernel, pytest, optional `discord.py>=2.7,<3`.

## Global Constraints
- Keep simulation authoritative and Discord-free.
- Do not read ordinary message content.
- No bot token or guild ID in source.
- `/act` parser is deterministic in this slice; no LLM dependency.
- Reuse interaction ID as GameService `external_id`.

### Task 1: Deterministic command parser
- Create `src/samseberpg/parser.py`, `tests/test_parser.py`.
- [ ] Write failing tests for look/move/take/drop Russian and English forms plus unknown input.
- [ ] Run focused tests and verify RED.
- [ ] Implement `parse_action(text, player_id) -> CanonicalAction | None` with explicit normalized prefixes.
- [ ] Run focused/full tests and verify GREEN.

### Task 2: Discord presentation and pure application adapter
- Create `src/samseberpg/presentation.py`, `src/samseberpg/discord_app.py`, `tests/test_discord_app.py`.
- [ ] Write failing tests for `/look`, `/me`, successful `/act`, duplicate interaction replay, and unknown input producing no event.
- [ ] Run RED.
- [ ] Implement bounded renderers and `DiscordGameApplication` orchestration only.
- [ ] Run focused/full tests and verify GREEN.

### Task 3: Thin discord.py runtime shell
- Create `src/samseberpg/discord_bot.py`; modify `pyproject.toml`.
- [ ] Add optional `discord = ["discord.py>=2.7,<3"]` dependency.
- [ ] Implement Bot/CommandTree setup for `/look`, `/me`, `/act`; use `Intents.none()` and environment configuration.
- [ ] Guild-sync when `DISCORD_GUILD_ID` is present, global sync otherwise.
- [ ] Add generic callback error handling without exposing internals.
- [ ] Verify only `discord_bot.py` imports discord.

### Task 4: Runbook and completion verification
- Modify `README.md`.
- [ ] Document Developer Portal prerequisites, `pip install -e '.[dev,discord]'`, token/guild env vars, and `python -m samseberpg.discord_bot`.
- [ ] Run compileall, full pytest, demo, and import-isolation grep.
