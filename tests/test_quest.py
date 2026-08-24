from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService
from samseberpg.quest import QUEST_TYPE, QuestService


def make_services(tmp_path: Path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))
    return db, GameService(db, clock), QuestService(db, clock)


def take_firewood(game: GameService, player_id: str, count: int) -> None:
    for index in range(1, count + 1):
        result = game.execute(
            CanonicalAction(
                actor_id=player_id,
                action_type=ActionType.TAKE,
                target_id=f"firewood_{index}",
            )
        )
        assert result.success is True


def test_quest_is_available_then_accepts_and_persists(tmp_path: Path) -> None:
    db, game, quest = make_services(tmp_path)
    player = game.register_player("local-a", "Ren")

    available = quest.get_state(player)
    assert available.quest_type == QUEST_TYPE
    assert available.status == "available"
    assert available.required_firewood == 5
    assert available.owned_firewood == 0

    accepted = quest.accept(player, external_id="quest-accept-1")
    assert accepted.success is True
    assert accepted.code == "OK"
    assert accepted.state.status == "active"

    reopened = QuestService(db, quest.clock)
    assert reopened.get_state(player).status == "active"


def test_turn_in_requires_five_owned_firewood(tmp_path: Path) -> None:
    _, game, quest = make_services(tmp_path)
    player = game.register_player("local-a", "Ren")
    assert quest.accept(player).success
    take_firewood(game, player, 4)

    result = quest.turn_in(player, external_id="turn-in-too-early")

    assert result.success is False
    assert result.code == "INSUFFICIENT_FIREWOOD"
    assert result.state.status == "active"
    assert result.state.owned_firewood == 4


def test_successful_turn_in_is_exact_once_and_writes_consequence(tmp_path: Path) -> None:
    db, game, quest = make_services(tmp_path)
    player = game.register_player("local-a", "Ren")
    assert quest.accept(player).success
    take_firewood(game, player, 5)

    first = quest.turn_in(player, external_id="turn-in-1")
    second = quest.turn_in(player, external_id="turn-in-2")

    assert first.success is True
    assert first.code == "OK"
    assert first.state.status == "completed"
    assert first.state.owned_firewood == 0
    assert second.success is False
    assert second.code == "ALREADY_COMPLETED"

    with db.connect() as conn:
        coins = conn.execute(
            "SELECT coins FROM players WHERE actor_id = ?", (player,)
        ).fetchone()[0]
        relation = conn.execute(
            "SELECT trust FROM relations WHERE source_actor_id = 'npc_oren' AND target_actor_id = ?",
            (player,),
        ).fetchone()[0]
        memories = conn.execute(
            "SELECT fact FROM npc_memories WHERE npc_actor_id = 'npc_oren' AND subject_actor_id = ?",
            (player,),
        ).fetchall()
        owner_count = conn.execute(
            "SELECT COUNT(*) FROM entities WHERE entity_type = 'firewood' AND owner_actor_id = 'npc_oren'"
        ).fetchone()[0]
        quest_events = conn.execute(
            "SELECT action_type, success FROM action_events WHERE actor_id = ? AND action_type LIKE 'QUEST_%' ORDER BY id",
            (player,),
        ).fetchall()

    assert coins == 15
    assert relation == 10
    assert [row[0] for row in memories] == ["The player brought Oren the requested firewood."]
    assert owner_count == 5
    assert [tuple(row) for row in quest_events] == [
        ("QUEST_ACCEPT", 1),
        ("QUEST_TURN_IN", 1),
        ("QUEST_TURN_IN", 0),
    ]


def test_duplicate_external_id_replays_without_duplicate_quest_mutation(tmp_path: Path) -> None:
    db, game, quest = make_services(tmp_path)
    player = game.register_player("local-a", "Ren")

    first = quest.accept(player, external_id="same-accept")
    replay = quest.accept(player, external_id="same-accept")

    assert first.success is True
    assert replay.success is True
    assert replay.replayed is True
    assert replay.event_id == first.event_id
    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM quests WHERE player_actor_id = ? AND quest_type = ?",
            (player, QUEST_TYPE),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM action_events WHERE external_id = 'same-accept'"
        ).fetchone()[0] == 1
