# World Digest v0 — Design Specification

## Goal

Make returning to the village visibly different from opening a static save. A player can ask what changed since their own last gameplay activity and receive a deterministic world digest derived only from canonical state and `action_events`.

## Product hypothesis

The smallest useful proof of the persistent-world fantasy is: Player A leaves; Player B changes the shared world; time advances; when A returns, one command tells A what other players changed and where NPCs are now.

## Scope

Included:
- on-demand `/news` Discord command;
- event-log anchor derived from the requesting player's latest `action_events.id`;
- successful notable actions by other players after that anchor;
- current persistent object damage;
- current NPC location/activity after normal lazy catch-up;
- deterministic Russian rendering;
- bounded output suitable for Discord.

Deferred:
- scheduled 09:00 push delivery;
- external weather data;
- LLM-generated newspaper prose;
- rumors, quests, autonomous event generation;
- separate read-receipt/checkpoint table;
- full historical archive UI.

## Anchor semantics

`since_event_id` is the maximum action event ID produced by the requesting player. If the player has never produced an event, it is `0`.

This means `/news` answers approximately "what changed after my last gameplay action" without introducing mutable UI checkpoints. Calling `/news` repeatedly is read-only and deterministic for the same world state.

## Notable event policy

v0 includes successful actions by other players with action types:
- `THROW`;
- `GIVE`;
- `BUY`.

Movement, LOOK, TAKE/DROP, USE and TALK are omitted from the newspaper to avoid noise. The latest 8 matching events are returned, ordered chronologically. The digest records how many additional matching events were omitted.

Each entry uses canonical event summary plus actor name, time and location ID. No LLM rewrites event history.

## Persistent state snapshot

The digest also reports any entity whose canonical `state_json.condition` is an integer below 100. This allows persistent damage to remain visible even if its original event is older than the player's anchor.

After catch-up, all NPCs are listed with current location and activity. This makes real-time schedules visible in the same return experience.

## Architecture

Add `src/samseberpg/digest.py` containing read-model dataclasses and `WorldDigestService`. It depends on `GameService` only to trigger normal `observe(player_id)` catch-up, then performs read-only SQLite queries through the game's database.

Discord application gets `handle_news(discord_user_id, display_name)`. Discord runtime registers `/news` with no privileged message intents.

The digest layer never mutates canonical gameplay state and never writes action events.

## Definition of Done

A deterministic two-player test proves:
1. A has a last action anchor.
2. B later damages the tavern sign.
3. Clock advances so NPC schedules change.
4. A's `/news` contains B's THROW, the damaged sign condition and current changed NPC positions/activity.
5. A's own actions are not reported as world news.
6. Repeating `/news` without state changes returns the same content.
7. Existing gameplay/progression/TALK semantics remain unchanged.
