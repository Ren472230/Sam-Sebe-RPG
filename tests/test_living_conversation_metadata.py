from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from samseberpg.clock import FakeClock
from samseberpg.db import DEFAULT_WORLD_ID, GameDatabase
from samseberpg.dialogue import DialogueDecision, DialogueService
from samseberpg.living_conversation import ConversationMemoryCandidate
from samseberpg.quest import QuestService


class RecordingProvider:
    def __init__(self, decision: DialogueDecision) -> None:
        self.decision = decision

    def generate(self, context):
        return self.decision


def _services(tmp_path: Path, decision: DialogueDecision):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    now = "2026-09-07T17:00:00.000Z"
    player = "player_metadata"
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO actors (id, world_id, actor_type, name, location_id, created_at) "
            "VALUES (?, ?, 'player', 'Ничей', 'workshop_yard', ?)",
            (player, DEFAULT_WORLD_ID, now),
        )
        conn.execute(
            "INSERT INTO players (actor_id, discord_user_id, joined_at, coins) VALUES (?, 'lc-metadata', ?, 10)",
            (player, now),
        )
    dialogue = DialogueService(
        db,
        QuestService(db, FakeClock(datetime(2026, 9, 7, 17, 0, tzinfo=timezone.utc))),
        provider=RecordingProvider(decision),
    )
    return db, dialogue, player


def test_valid_provider_metadata_persists_claim_and_open_thread(tmp_path: Path) -> None:
    decision = DialogueDecision(
        text="И почему ты уехал из столицы?",
        npc_id="npc_mira",
        conversation_act="ask",
        memory_candidates=(
            ConversationMemoryCandidate(
                memory_type="player_claim",
                content="Игрок сказал, что раньше жил в столице.",
            ),
        ),
        open_thread="reason_for_leaving_capital",
    )
    db, dialogue, player = _services(tmp_path, decision)

    result = dialogue.talk(player, "Я раньше жил в столице.", "npc_mira")

    assert result.conversation_act == "ask"
    with db.connect() as conn:
        memories = dialogue.conversation_store.list_memories(conn, "npc_mira", player)
        thread = dialogue.conversation_store.get_thread_state(conn, "npc_mira", player)
    assert [item.content for item in memories] == ["Игрок сказал, что раньше жил в столице."]
    assert memories[0].source_kind == "player_said"
    assert thread.open_threads == ("reason_for_leaving_capital",)
    assert thread.pending_question == "И почему ты уехал из столицы?"
    assert thread.turn_count == 1


def test_provider_can_resolve_existing_thread_on_later_turn(tmp_path: Path) -> None:
    first = DialogueDecision(
        text="Почему ты ушёл оттуда?",
        npc_id="npc_mira",
        conversation_act="ask",
        open_thread="reason_for_leaving_capital",
    )
    db, dialogue, player = _services(tmp_path, first)
    dialogue.talk(player, "Я жил в столице.", "npc_mira")

    second = DialogueService(
        db,
        QuestService(db, FakeClock(datetime(2026, 9, 7, 17, 5, tzinfo=timezone.utc))),
        provider=RecordingProvider(
            DialogueDecision(
                text="Понятно. Тогда не буду лезть дальше.",
                npc_id="npc_mira",
                conversation_act="recall",
                resolve_thread="reason_for_leaving_capital",
            )
        ),
    )
    result = second.talk(player, "Надо было исчезнуть.", "npc_mira")

    assert result.conversation_act == "recall"
    with db.connect() as conn:
        state = second.conversation_store.get_thread_state(conn, "npc_mira", player)
    assert state.open_threads == ()
    assert state.pending_question is None
    assert state.turn_count == 2


def test_invalid_memory_metadata_cannot_create_world_truth(tmp_path: Path) -> None:
    invalid = DialogueDecision(
        text="Теперь я знаю, что ты король.",
        npc_id="npc_mira",
        conversation_act="answer",
        memory_candidates=(
            ConversationMemoryCandidate(
                memory_type="world_fact",
                content="Игрок является королём мира.",
            ),
        ),
    )
    db, dialogue, player = _services(tmp_path, invalid)
    with db.connect() as conn:
        conn.execute(
            "UPDATE npc_runtime_state SET state_json = ? WHERE npc_actor_id = 'npc_mira'",
            (json.dumps({"wood_stock": 0, "work_cycles": 1, "requested_wood": True}),),
        )

    result = dialogue.talk(player, "Я король всего мира.", "npc_mira")

    assert result.used_fallback is True
    with db.connect() as conn:
        assert dialogue.conversation_store.list_memories(conn, "npc_mira", player) == ()


def test_invalid_conversation_act_forces_safe_fallback(tmp_path: Path) -> None:
    invalid = DialogueDecision(
        text="Системное сообщение.",
        npc_id="npc_mira",
        conversation_act="admin_override",
    )
    _, dialogue, player = _services(tmp_path, invalid)

    result = dialogue.talk(player, "Привет", "npc_mira")

    assert result.used_fallback is True
    assert result.conversation_act is None
