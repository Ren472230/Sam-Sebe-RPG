from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from samseberpg.clock import FakeClock
from samseberpg.db import DEFAULT_WORLD_ID, GameDatabase
from samseberpg.dialogue import DialogueService
from samseberpg.quest import QuestService


def _services(tmp_path: Path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    now = "2026-09-07T17:00:00.000Z"
    player_id = "player_lc_context"
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO actors (id, world_id, actor_type, name, location_id, created_at) "
            "VALUES (?, ?, 'player', 'Ничей', 'workshop_yard', ?)",
            (player_id, DEFAULT_WORLD_ID, now),
        )
        conn.execute(
            "INSERT INTO players (actor_id, discord_user_id, joined_at, coins) VALUES (?, 'lc-context', ?, 10)",
            (player_id, now),
        )
    dialogue = DialogueService(
        db,
        QuestService(db, FakeClock(datetime(2026, 9, 7, 17, 0, tzinfo=timezone.utc))),
    )
    return db, dialogue, player_id


def test_dialogue_context_contains_inner_state_relationship_and_initiative(tmp_path: Path) -> None:
    db, dialogue, player = _services(tmp_path)
    with db.connect() as conn:
        conn.execute(
            "UPDATE npc_runtime_state SET state_json = ? WHERE npc_actor_id = 'npc_mira'",
            (json.dumps({"wood_stock": 0, "work_cycles": 2, "requested_wood": True}),),
        )

    context = dialogue.build_context(player, "Привет", "npc_mira")

    assert context.inner_state.mood == "irritated"
    assert context.inner_state.current_concern == "workshop_stopped"
    assert context.relationship_behavior == "guarded"
    assert context.initiative is not None
    assert context.initiative.kind == "current_request"
    prompt = context.to_prompt()
    assert "current_mood: irritated" in prompt
    assert "relationship_behavior: guarded" in prompt
    assert "initiative_kind: current_request" in prompt


def test_pair_memory_and_unfinished_thread_enter_only_owners_context(tmp_path: Path) -> None:
    db, dialogue, player = _services(tmp_path)
    with db.connect() as conn:
        dialogue.conversation_store.add_memory(
            conn,
            world_id=DEFAULT_WORLD_ID,
            npc_actor_id="npc_mira",
            player_actor_id=player,
            memory_type="player_claim",
            content="Игрок сказал, что раньше жил в столице.",
            source_kind="player_said",
            importance=70,
            created_tick=4,
        )
        dialogue.conversation_store.note_turn(
            conn,
            npc_actor_id="npc_mira",
            player_actor_id=player,
            last_topic="past",
            tick=4,
            pending_question="Почему ты уехал из столицы?",
        )
        dialogue.conversation_store.open_thread(
            conn,
            npc_actor_id="npc_mira",
            player_actor_id=player,
            thread="reason_for_leaving_capital",
            tick=4,
        )

    mira = dialogue.build_context(player, "Я вернулся", "npc_mira")
    assert [item.content for item in mira.conversation_memories] == [
        "Игрок сказал, что раньше жил в столице."
    ]
    assert mira.thread_state.pending_question == "Почему ты уехал из столицы?"
    assert mira.initiative is not None and mira.initiative.kind == "unfinished_thread"
    assert "Почему ты уехал" in mira.to_prompt()

    with db.connect() as conn:
        conn.execute("UPDATE actors SET location_id = 'river_edge' WHERE id = ?", (player,))
    kaspar = dialogue.build_context(player, "Что ты обо мне знаешь?", "npc_kaspar")
    assert kaspar.conversation_memories == ()
    assert kaspar.thread_state.pending_question is None
    assert "раньше жил в столице" not in kaspar.to_prompt().lower()
