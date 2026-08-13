from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_database_bootstrap_creates_player_and_initial_stone(tmp_path: Path) -> None:
    try:
        from samseberpg.db import GameDatabase
    except ImportError as exc:
        pytest.fail(f"GameDatabase is not implemented yet: {exc}")

    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty()

    player = db.fetch_player("player_1")
    stone = db.fetch_entity("stone_flat_1")

    assert player is not None
    assert player["location_id"] == "workshop_yard"
    assert stone is not None
    assert stone["location_id"] == "workshop_yard"


def _make_game(tmp_path: Path, seed: int = 0):
    from samseberpg.db import GameDatabase
    try:
        from samseberpg.game import GameService
    except ImportError as exc:
        pytest.fail(f"GameService is not implemented yet: {exc}")

    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty()
    return db, GameService(db, seed=seed)


def test_cannot_take_item_from_another_location(tmp_path: Path) -> None:
    from samseberpg.domain import ActionType, CanonicalAction

    db, game = _make_game(tmp_path)
    result = game.execute(
        CanonicalAction(actor_id="player_1", action_type=ActionType.TAKE, item_id="apple_1")
    )

    assert result.success is False
    assert result.code == "ITEM_NOT_PRESENT"
    assert db.list_inventory("player_1") == []
    assert db.list_events("player_1")[-1]["result_code"] == "ITEM_NOT_PRESENT"


def test_take_moves_item_to_inventory_and_appends_success_event(tmp_path: Path) -> None:
    from samseberpg.domain import ActionType, CanonicalAction

    db, game = _make_game(tmp_path)
    result = game.execute(
        CanonicalAction(actor_id="player_1", action_type=ActionType.TAKE, item_id="stone_flat_1")
    )

    assert result.success is True
    assert [row["entity_id"] for row in db.list_inventory("player_1")] == ["stone_flat_1"]
    assert db.fetch_entity("stone_flat_1")["location_id"] is None
    event = db.list_events("player_1")[-1]
    assert event["success"] == 1
    assert event["result_code"] == "OK"


def test_drop_returns_owned_item_to_current_location(tmp_path: Path) -> None:
    from samseberpg.domain import ActionType, CanonicalAction

    db, game = _make_game(tmp_path)
    game.execute(CanonicalAction(actor_id="player_1", action_type=ActionType.TAKE, item_id="stone_flat_1"))
    result = game.execute(
        CanonicalAction(actor_id="player_1", action_type=ActionType.DROP, item_id="stone_flat_1")
    )

    assert result.success is True
    assert db.list_inventory("player_1") == []
    assert db.fetch_entity("stone_flat_1")["location_id"] == "workshop_yard"


def test_move_to_connected_location_updates_player_position(tmp_path: Path) -> None:
    from samseberpg.domain import ActionType, CanonicalAction

    db, game = _make_game(tmp_path)
    result = game.execute(
        CanonicalAction(
            actor_id="player_1",
            action_type=ActionType.MOVE,
            destination_id="village_square",
        )
    )

    assert result.success is True
    assert db.fetch_player("player_1")["location_id"] == "village_square"


def test_move_rejects_non_connected_location(tmp_path: Path) -> None:
    from samseberpg.domain import ActionType, CanonicalAction

    db, game = _make_game(tmp_path)
    result = game.execute(
        CanonicalAction(
            actor_id="player_1",
            action_type=ActionType.MOVE,
            destination_id="river_edge",
        )
    )

    assert result.success is False
    assert result.code == "INVALID_DESTINATION"
    assert db.fetch_player("player_1")["location_id"] == "workshop_yard"


def test_wait_advances_world_time(tmp_path: Path) -> None:
    from samseberpg.domain import ActionType, CanonicalAction

    db, game = _make_game(tmp_path)
    before = db.get_world_time()
    result = game.execute(CanonicalAction(actor_id="player_1", action_type=ActionType.WAIT))

    assert result.success is True
    assert db.get_world_time() == before + 1


def test_look_returns_entities_in_current_location_only(tmp_path: Path) -> None:
    from samseberpg.domain import ActionType, CanonicalAction

    _db, game = _make_game(tmp_path)
    result = game.execute(CanonicalAction(actor_id="player_1", action_type=ActionType.LOOK))

    assert result.success is True
    ids = {entity["entity_id"] for entity in result.data["entities"]}
    assert "mira_craftswoman" in ids
    assert "target_barrel" in ids
    assert "stone_flat_1" in ids
    assert "oren_innkeeper" not in ids


def test_database_enables_wal_and_busy_timeout_for_local_concurrency(tmp_path: Path) -> None:
    from samseberpg.db import GameDatabase

    db = GameDatabase(tmp_path / "game.db")
    db.initialize()

    with db.connect() as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]

    assert journal_mode.casefold() == "wal"
    assert busy_timeout >= 5000
