# NPC TALK v0 — Design Specification

## Goal

Make the current village feel like an RPG rather than only a systems sandbox by adding one canonical NPC interaction that is safe for persistence and future dialogue/memory layers.

A player can address a visible NPC through explicit grammar or natural-language intent. The deterministic core decides whether conversation is possible, records the interaction, and changes structured relationship familiarity. No LLM is allowed to invent state changes.

## Scope

Included: canonical `TALK`; present NPC targets only; exact RU/EN TALK/SAY forms; semantic TALK; NPC->player `familiarity +1`; evidence containing target, original utterance, current NPC activity and relation delta; Discord integration; provenance suitable for later memory.

Deferred: generated dialogue, dialogue trees, quests, persuasion checks, raw-chat memory, LLM-controlled relationship mutation and autonomous NPC goals.

## Canonical behavior

`ActionType.TALK` uses `target_id` as NPC actor ID and preserves player input in `source_text`.

Preconditions: target exists, is NPC, and is present at the player's location.

Success applies bounded `familiarity += 1` using the existing relation helper and records structured evidence. Failures are typed/non-mutating: `TARGET_ACTOR_NOT_FOUND`, `TARGET_NOT_NPC`, `TARGET_NOT_PRESENT`.

## Parser and semantic guardrails

Exact forms: `говорить npc_mira`, `talk npc_mira`, `сказать npc_mira привет`, `say npc_mira hello there`.

Semantic `TALK` is canonicalized only when `target_id` is a currently visible NPC. A visible player target is rejected because Discord itself is the player-to-player communication channel.

## Definition of Done

A player can naturally or explicitly address Mira/Oren/Kaspar when physically present; the interaction is a canonical persistent action, records evidence for future memory, changes structured familiarity exactly once under idempotency, and cannot target absent/non-NPC actors through the semantic layer.
