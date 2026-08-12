from pathlib import Path

from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path: Path) -> tuple[GameDatabase, GameService]:
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty()
    return db, GameService(db, seed=7)


def test_initialize_creates_required_tables_and_bootstrap_world(tmp_path: Path) -> None:
    db, _ = make_game(tmp_path)

    assert db.list_tables() == {
        "abilities",
        "achievements",
        "action_events",
        "behavior_profiles",
        "entities",
        "inventory",
        "player_state",
        "relations",
        "world_meta",
    }

    player = db.fetch_player("player_1")
    stone = db.fetch_entity("stone_flat_1")

    assert player is not None
    assert player["location_id"] == "workshop_yard"
    assert stone is not None
    assert stone["location_id"] == "workshop_yard"
    assert stone["entity_type"] == "item"


def test_take_rejects_item_from_another_location_and_logs_failure(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)

    result = game.execute(
        CanonicalAction("player_1", ActionType.TAKE, item_id="pinecone_1")
    )

    assert result.success is False
    assert result.code == "ITEM_NOT_PRESENT"
    assert db.list_inventory("player_1") == []
    event = db.list_events("player_1")[-1]
    assert event["success"] is False
    assert event["result_code"] == "ITEM_NOT_PRESENT"


def test_take_and_drop_move_item_between_world_and_inventory(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)

    take = game.execute(
        CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1")
    )
    assert take.success is True
    assert db.list_inventory("player_1") == ["stone_flat_1"]
    assert db.fetch_entity("stone_flat_1")["location_id"] is None

    drop = game.execute(
        CanonicalAction("player_1", ActionType.DROP, item_id="stone_flat_1")
    )
    assert drop.success is True
    assert db.list_inventory("player_1") == []
    assert db.fetch_entity("stone_flat_1")["location_id"] == "workshop_yard"


def test_move_only_allows_connected_locations(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)

    invalid = game.execute(
        CanonicalAction(
            "player_1", ActionType.MOVE, destination_id="river_edge"
        )
    )
    assert invalid.success is False
    assert invalid.code == "INVALID_DESTINATION"
    assert db.fetch_player("player_1")["location_id"] == "workshop_yard"

    valid = game.execute(
        CanonicalAction(
            "player_1", ActionType.MOVE, destination_id="village_square"
        )
    )
    assert valid.success is True
    assert db.fetch_player("player_1")["location_id"] == "village_square"


def test_wait_advances_world_time(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)

    result = game.execute(
        CanonicalAction("player_1", ActionType.WAIT, modifiers={"ticks": 3})
    )

    assert result.success is True
    assert db.get_world_time() == 3


def test_look_returns_visible_entities_and_connected_exits(tmp_path: Path) -> None:
    _db, game = make_game(tmp_path)

    result = game.execute(CanonicalAction("player_1", ActionType.LOOK))

    assert result.success is True
    assert result.data["exits"] == ["village_square"]
    entity_ids = {entity["entity_id"] for entity in result.data["entities"]}
    assert {"mira_craftswoman", "target_barrel", "stone_flat_1"} <= entity_ids
