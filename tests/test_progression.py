from pathlib import Path

from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path: Path, seed: int = 1) -> tuple[GameDatabase, GameService]:
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty()
    return db, GameService(db, seed=seed)


def ensure_owned(db: GameDatabase, game: GameService, item_id: str) -> None:
    if item_id in db.list_inventory("player_1"):
        return
    result = game.execute(CanonicalAction("player_1", ActionType.TAKE, item_id=item_id))
    assert result.success, result


def throw_once(
    db: GameDatabase, game: GameService, item_id: str, target_id: str, *, aimed: bool = False
):
    ensure_owned(db, game, item_id)
    return game.execute(
        CanonicalAction(
            "player_1",
            ActionType.THROW,
            item_id=item_id,
            target_id=target_id,
            modifiers={"aimed": aimed} if aimed else {},
        )
    )


def test_repetition_alone_does_not_unlock_specialization(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)

    for _ in range(12):
        result = throw_once(db, game, "stone_flat_1", "target_barrel")
        assert result.success

    assert db.has_achievement("player_1", "hand_remembers_arc") is False
    assert db.has_ability("player_1", "aimed_throw") is False

    profile = db.fetch_behavior_profile("player_1", "throwing")
    assert profile["attempts"] == 12
    assert len(profile["targets"]) == 1
    assert len(profile["projectile_types"]) == 1
    assert len(profile["locations"]) == 1


def test_varied_competent_throwing_unlocks_and_persists_aimed_throw(tmp_path: Path) -> None:
    db, game = make_game(tmp_path, seed=1)

    # Four throws in the workshop using two projectile types.
    for item_id in ["stone_flat_1", "stone_round_1"] * 2:
        assert throw_once(db, game, item_id, "target_barrel").success

    # Carry both projectiles to the square.
    ensure_owned(db, game, "stone_flat_1")
    ensure_owned(db, game, "stone_round_1")
    assert game.execute(
        CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")
    ).success

    for item_id in ["stone_flat_1", "stone_round_1"] * 2:
        assert throw_once(db, game, item_id, "target_sign").success

    # Carry both projectiles to the river.
    ensure_owned(db, game, "stone_flat_1")
    ensure_owned(db, game, "stone_round_1")
    assert game.execute(
        CanonicalAction("player_1", ActionType.MOVE, destination_id="river_edge")
    ).success

    for item_id in ["stone_flat_1", "stone_round_1"] * 2:
        assert throw_once(db, game, item_id, "target_post").success

    profile = db.fetch_behavior_profile("player_1", "throwing")
    assert profile["attempts"] == 12
    assert profile["hits"] >= 5
    assert set(profile["targets"]) == {"target_barrel", "target_sign", "target_post"}
    assert set(profile["projectile_types"]) == {"flat_stone", "round_stone"}
    assert set(profile["locations"]) == {"workshop_yard", "village_square", "river_edge"}

    assert db.has_achievement("player_1", "hand_remembers_arc") is True
    assert db.has_ability("player_1", "aimed_throw") is True

    reopened = GameDatabase(db.path)
    assert reopened.has_achievement("player_1", "hand_remembers_arc") is True
    assert reopened.has_ability("player_1", "aimed_throw") is True


def test_aimed_throw_requires_unlock_then_adds_accuracy(tmp_path: Path) -> None:
    db, game = make_game(tmp_path, seed=1)
    ensure_owned(db, game, "stone_flat_1")

    locked = game.execute(
        CanonicalAction(
            "player_1",
            ActionType.THROW,
            item_id="stone_flat_1",
            target_id="target_barrel",
            modifiers={"aimed": True},
        )
    )
    assert locked.success is False
    assert locked.code == "ACTION_NOT_UNLOCKED"

    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO abilities(player_id, ability_id, mechanic_json, unlocked_at)
            VALUES ('player_1', 'aimed_throw', '{"primitive":"MODIFY_ACCURACY","value":10}', 0)
            """
        )

    aimed = game.execute(
        CanonicalAction(
            "player_1",
            ActionType.THROW,
            item_id="stone_flat_1",
            target_id="target_barrel",
            modifiers={"aimed": True},
        )
    )
    assert aimed.success is True
    assert aimed.data["accuracy"] == 0.55
