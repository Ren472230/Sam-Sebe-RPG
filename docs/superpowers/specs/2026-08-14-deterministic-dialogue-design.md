# Deterministic NPC Dialogue v0 — Design Specification

## Goal

Make canonical TALK feel like an actual RPG conversation while preserving the authoritative-state boundary. NPC response text is a rendering of canonical activity + structured relationship state; it cannot change the world.

## Product hypothesis

A player should immediately notice that the same NPC responds differently after a gift or a conflict. This creates the first visible proof that NPC relationships matter beyond hidden numbers.

## Scope

Included:
- deterministic dialogue rendering for Mira, Oren and Kaspar;
- compact persona catalog in code;
- current NPC activity from TALK evidence;
- current structured familiarity/trust/affinity/conflict read from SQLite;
- a small set of relationship-sensitive response branches;
- Discord TALK response enriched with visual-novel-style dialogue;
- no additional state mutation or action event.

Deferred:
- LLM-generated dialogue;
- long-term prose memory;
- persuasion checks;
- quests/dialogue trees;
- generated secrets/lore;
- voice.

## Persona catalog

Mira: practical craftswoman, focused, warm only after familiarity/trust develops.

Oren: pragmatic innkeeper, socially attentive; clear warmth after positive trust and clear guardedness when conflict exists.

Kaspar: quiet forager, economical speech, references his current work/activity.

## Relationship branches

The renderer reads NPC -> player relation after canonical TALK has applied its `familiarity +1`.

Priority:
1. `conflict >= 4` or `trust <= -3`: guarded/conflict response;
2. `trust >= 2` or `affinity >= 1`: warmer response;
3. `familiarity >= 3`: familiar neutral response;
4. otherwise: first-contact/neutral response.

The original utterance may influence only presentation-level phrasing (for example a question containing `как дела` can produce an activity-oriented answer). It cannot change relation values or any canonical state.

## Architecture

Add `src/samseberpg/dialogue.py` with immutable persona/context models and `DialogueService.render(player_id, talk_result) -> str`.

The service reads current relations from `GameDatabase`. It does not write DB rows. `DiscordGameApplication.handle_act` detects a successful canonical TALK and appends the rendered dialogue before the normal world view.

## Definition of Done

- first TALK with Mira returns characterful text tied to her current activity;
- gifting food to Oren produces a warmer later TALK response;
- damaging Oren's tavern sign while he witnesses it produces a guarded later TALK response;
- repeated identical Discord interaction remains idempotent and does not add extra familiarity/events;
- dialogue rendering itself performs no DB writes;
- all existing digest/progression/TALK guardrails remain intact.
