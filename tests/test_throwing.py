from pathlib import Path

from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path: Path, name: str = "game.db", seed: int = 11):
    db = GameDatabase(tmp_path / name)
    db.initialize()
    db.bootstrap_if_empty()
    return db, GameService(db, seed=seed)


def take(game: GameService, item_id: str) -> None:
    result = game.execute(CanonicalAction("player_1", ActionType.TAKE, item_id=item_id))
    assert result.success


def test_throw_rejects_item_not_owned(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)

    result = game.execute(
        CanonicalAction(
            "player_1", ActionType.THROW, target_id="target_barrel", item_id="stone_flat_1"
        )
    )

    assert result.success is False
    assert result.code == "ITEM_NOT_OWNED"
    assert db.fetch_entity("stone_flat_1")["location_id"] == "workshop_yard"


def test_throw_rejects_non_projectile(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO entities(entity_id, entity_type, name, location_id, tags_json, state_json)
            VALUES ('hammer_1', 'item', 'Молоток', 'workshop_yard', '[\"tool\"]', '{}')
            """
        )
    take(game, "hammer_1")

    result = game.execute(
        CanonicalAction(
            "player_1", ActionType.THROW, target_id="target_barrel", item_id="hammer_1"
        )
    )

    assert result.success is False
    assert result.code == "ITEM_NOT_THROWABLE"
    assert db.list_inventory("player_1") == ["hammer_1"]


def test_throw_is_reproducible_with_same_seed(tmp_path: Path) -> None:
    db_a, game_a = make_game(tmp_path, "a.db", seed=23)
    db_b, game_b = make_game(tmp_path, "b.db", seed=23)
    take(game_a, "stone_flat_1")
    take(game_b, "stone_flat_1")

    result_a = game_a.execute(
        CanonicalAction(
            "player_1", ActionType.THROW, target_id="target_barrel", item_id="stone_flat_1"
        )
    )
    result_b = game_b.execute(
        CanonicalAction(
            "player_1", ActionType.THROW, target_id="target_barrel", item_id="stone_flat_1"
        )
    )

    assert result_a.success is True
    assert result_b.success is True
    assert result_a.data["hit"] == result_b.data["hit"]
    assert result_a.data["accuracy_roll"] == result_b.data["accuracy_roll"]


def test_throw_moves_item_back_to_location_and_records_evidence(tmp_path: Path) -> None:
    db, game = make_game(tmp_path, seed=3)
    take(game, "stone_flat_1")

    result = game.execute(
        CanonicalAction(
            "player_1", ActionType.THROW, target_id="target_barrel", item_id="stone_flat_1"
        )
    )

    assert result.success is True
    assert db.list_inventory("player_1") == []
    assert db.fetch_entity("stone_flat_1")["location_id"] == "workshop_yard"

    event = db.list_events("player_1")[-1]
    assert event["action_type"] == "THROW"
    assert event["behavior_tags"] == ["throwing", "improvised_projectile"]
    assert event["evidence"]["projectile_type"] == "flat_stone"
    assert event["evidence"]["target_id"] == "target_barrel"
    assert event["evidence"]["location_id"] == "workshop_yard"
    assert isinstance(event["evidence"]["hit"], bool)
    assert 0.0 <= event["evidence"]["accuracy_roll"] < 1.0


def test_rng_sequence_survives_service_restart(tmp_path: Path) -> None:
    db_a, game_a = make_game(tmp_path, "continuous.db", seed=41)
    db_b, game_b = make_game(tmp_path, "restarted.db", seed=41)

    take(game_a, "stone_flat_1")
    first_a = game_a.execute(
        CanonicalAction(
            "player_1", ActionType.THROW, target_id="target_barrel", item_id="stone_flat_1"
        )
    )
    take(game_a, "stone_flat_1")
    second_a = game_a.execute(
        CanonicalAction(
            "player_1", ActionType.THROW, target_id="target_barrel", item_id="stone_flat_1"
        )
    )

    take(game_b, "stone_flat_1")
    first_b = game_b.execute(
        CanonicalAction(
            "player_1", ActionType.THROW, target_id="target_barrel", item_id="stone_flat_1"
        )
    )
    restarted = GameService(db_b, seed=999)
    take(restarted, "stone_flat_1")
    second_b = restarted.execute(
        CanonicalAction(
            "player_1", ActionType.THROW, target_id="target_barrel", item_id="stone_flat_1"
        )
    )

    assert first_a.data["accuracy_roll"] == first_b.data["accuracy_roll"]
    assert second_a.data["accuracy_roll"] == second_b.data["accuracy_roll"]
