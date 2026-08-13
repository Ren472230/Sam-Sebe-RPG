from __future__ import annotations

import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path: Path, seed: int = 0, name: str = "game.db") -> tuple[GameDatabase, GameService]:
    db = GameDatabase(tmp_path / name)
    db.initialize()
    db.bootstrap_if_empty()
    return db, GameService(db, seed=seed)


def test_throw_rejects_projectile_not_owned_by_player(tmp_path: Path) -> None:
    _db, game = make_game(tmp_path)
    result = game.execute(
        CanonicalAction(
            actor_id="player_1",
            action_type=ActionType.THROW,
            item_id="stone_flat_1",
            target_id="target_barrel",
        )
    )

    assert result.success is False
    assert result.code == "ITEM_NOT_OWNED"


def test_throw_rejects_item_without_projectile_tag(tmp_path: Path) -> None:
    _db, game = make_game(tmp_path)
    game.execute(CanonicalAction(actor_id="player_1", action_type=ActionType.MOVE, destination_id="village_square"))
    game.execute(CanonicalAction(actor_id="player_1", action_type=ActionType.TAKE, item_id="apple_1"))

    result = game.execute(
        CanonicalAction(
            actor_id="player_1",
            action_type=ActionType.THROW,
            item_id="apple_1",
            target_id="oren_innkeeper",
        )
    )

    assert result.success is False
    assert result.code == "ITEM_NOT_THROWABLE"


def test_throw_rejects_target_outside_current_location(tmp_path: Path) -> None:
    _db, game = make_game(tmp_path)
    game.execute(CanonicalAction(actor_id="player_1", action_type=ActionType.TAKE, item_id="stone_flat_1"))

    result = game.execute(
        CanonicalAction(
            actor_id="player_1",
            action_type=ActionType.THROW,
            item_id="stone_flat_1",
            target_id="oren_innkeeper",
        )
    )

    assert result.success is False
    assert result.code == "TARGET_NOT_PRESENT"


def test_valid_throw_places_item_in_location_and_logs_evidence(tmp_path: Path) -> None:
    db, game = make_game(tmp_path, seed=1)
    game.execute(CanonicalAction(actor_id="player_1", action_type=ActionType.TAKE, item_id="stone_flat_1"))

    result = game.execute(
        CanonicalAction(
            actor_id="player_1",
            action_type=ActionType.THROW,
            item_id="stone_flat_1",
            target_id="target_barrel",
        )
    )

    assert result.success is True
    assert result.code == "OK"
    assert result.data["hit"] is True
    assert db.list_inventory("player_1") == []
    assert db.fetch_entity("stone_flat_1")["location_id"] == "workshop_yard"

    event = db.list_events("player_1")[-1]
    assert event["action_type"] == "THROW"
    assert event["success"] == 1
    assert "throw" in json.loads(event["behavior_tags_json"])
    evidence = json.loads(event["evidence_json"])
    assert evidence["hit"] is True
    assert evidence["accuracy_chance"] == 0.45
    assert 0 <= evidence["accuracy_roll"] < 1


def test_throw_resolution_is_reproducible_with_same_seed(tmp_path: Path) -> None:
    results = []
    for index in range(2):
        _db, game = make_game(tmp_path, seed=42, name=f"game-{index}.db")
        game.execute(CanonicalAction(actor_id="player_1", action_type=ActionType.TAKE, item_id="stone_flat_1"))
        result = game.execute(
            CanonicalAction(
                actor_id="player_1",
                action_type=ActionType.THROW,
                item_id="stone_flat_1",
                target_id="target_barrel",
            )
        )
        results.append((result.data.get("hit"), result.data.get("accuracy_roll")))

    assert results[0] == results[1]
    assert results[0][1] is not None
