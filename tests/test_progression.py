from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(db_path: Path, *, seed: int = 1) -> tuple[GameDatabase, GameService]:
    db = GameDatabase(db_path)
    db.initialize()
    clock = FakeClock(datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc))
    return db, GameService(db, clock, seed=seed)


def throw_and_retake(game: GameService, player: str, item_id: str, target_id: str) -> None:
    thrown = game.execute(
        CanonicalAction(
            actor_id=player,
            action_type=ActionType.THROW,
            target_id=target_id,
            item_id=item_id,
        )
    )
    assert thrown.success, thrown
    retaken = game.execute(
        CanonicalAction(actor_id=player, action_type=ActionType.TAKE, target_id=item_id)
    )
    assert retaken.success, retaken


def test_repetition_alone_does_not_unlock_throwing_specialization(tmp_path: Path) -> None:
    db, game = make_game(tmp_path / "world.sqlite3")
    player = game.register_player("discord-a", "Ari")
    assert game.execute(
        CanonicalAction(actor_id=player, action_type=ActionType.TAKE, target_id="stone_flat_1")
    ).success

    for _ in range(12):
        throw_and_retake(game, player, "stone_flat_1", "npc_mira")

    with db.connect() as conn:
        achievements = conn.execute(
            "SELECT achievement_id FROM achievements WHERE actor_id = ?", (player,)
        ).fetchall()
        abilities = conn.execute(
            "SELECT ability_id FROM abilities WHERE actor_id = ?", (player,)
        ).fetchall()

    assert achievements == []
    assert abilities == []


def test_varied_competent_throwing_unlocks_achievement_and_ability(tmp_path: Path) -> None:
    db, game = make_game(tmp_path / "world.sqlite3", seed=1)
    player = game.register_player("discord-a", "Ari")
    for item_id in ("stone_flat_1", "wood_block_1"):
        assert game.execute(
            CanonicalAction(actor_id=player, action_type=ActionType.TAKE, target_id=item_id)
        ).success

    for index in range(4):
        throw_and_retake(
            game,
            player,
            ("stone_flat_1", "wood_block_1")[index % 2],
            "npc_mira",
        )

    assert game.execute(
        CanonicalAction(
            actor_id=player,
            action_type=ActionType.MOVE,
            destination_id="village_square",
        )
    ).success
    for index in range(4):
        throw_and_retake(
            game,
            player,
            ("stone_flat_1", "wood_block_1")[index % 2],
            "npc_oren",
        )

    assert game.execute(
        CanonicalAction(
            actor_id=player,
            action_type=ActionType.MOVE,
            destination_id="river_edge",
        )
    ).success
    for index in range(4):
        throw_and_retake(
            game,
            player,
            ("stone_flat_1", "wood_block_1")[index % 2],
            "npc_kaspar",
        )

    with db.connect() as conn:
        throw_events = conn.execute(
            "SELECT evidence_json FROM action_events "
            "WHERE actor_id = ? AND action_type = 'THROW' AND success = 1 ORDER BY id",
            (player,),
        ).fetchall()
        achievement = conn.execute(
            "SELECT achievement_id, evidence_json FROM achievements "
            "WHERE actor_id = ? AND achievement_id = 'hand_remembers_arc'",
            (player,),
        ).fetchone()
        ability = conn.execute(
            "SELECT ability_id, source_achievement_id FROM abilities "
            "WHERE actor_id = ? AND ability_id = 'aimed_throw'",
            (player,),
        ).fetchone()

    assert len(throw_events) == 12
    assert sum(bool(json.loads(row[0])["hit"]) for row in throw_events) >= 5
    assert achievement is not None
    evidence = json.loads(achievement[1])
    assert evidence == {
        "attempts": 12,
        "distinct_locations": 3,
        "distinct_projectile_types": 2,
        "distinct_targets": 3,
        "hits": 6,
    }
    assert tuple(ability) == ("aimed_throw", "hand_remembers_arc")
