from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path: Path, seed: int = 1) -> tuple[GameDatabase, GameService]:
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty()
    return db, GameService(db, seed=seed)


def progression_service(db: GameDatabase):
    try:
        from samseberpg.progression import ProgressionService
    except ImportError as exc:
        pytest.fail(f"ProgressionService is not implemented yet: {exc}")
    return ProgressionService(db)


def take_and_throw(game: GameService, item_id: str, target_id: str) -> None:
    take = game.execute(
        CanonicalAction(actor_id="player_1", action_type=ActionType.TAKE, item_id=item_id)
    )
    assert take.success is True
    throw = game.execute(
        CanonicalAction(
            actor_id="player_1",
            action_type=ActionType.THROW,
            item_id=item_id,
            target_id=target_id,
        )
    )
    assert throw.success is True


def perform_qualifying_pattern(game: GameService) -> None:
    for _ in range(3):
        take_and_throw(game, "stone_flat_1", "target_barrel")
        take_and_throw(game, "stone_round_1", "mira_craftswoman")

    assert game.execute(
        CanonicalAction(actor_id="player_1", action_type=ActionType.TAKE, item_id="stone_flat_1")
    ).success
    assert game.execute(
        CanonicalAction(actor_id="player_1", action_type=ActionType.TAKE, item_id="stone_round_1")
    ).success
    assert game.execute(
        CanonicalAction(
            actor_id="player_1",
            action_type=ActionType.MOVE,
            destination_id="village_square",
        )
    ).success

    for _ in range(3):
        throw_flat = game.execute(
            CanonicalAction(
                actor_id="player_1",
                action_type=ActionType.THROW,
                item_id="stone_flat_1",
                target_id="oren_innkeeper",
            )
        )
        assert throw_flat.success
        assert game.execute(
            CanonicalAction(actor_id="player_1", action_type=ActionType.TAKE, item_id="stone_flat_1")
        ).success

        throw_round = game.execute(
            CanonicalAction(
                actor_id="player_1",
                action_type=ActionType.THROW,
                item_id="stone_round_1",
                target_id="oren_innkeeper",
            )
        )
        assert throw_round.success
        assert game.execute(
            CanonicalAction(actor_id="player_1", action_type=ActionType.TAKE, item_id="stone_round_1")
        ).success


def test_repetition_alone_does_not_unlock_throwing_progression(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    for _ in range(12):
        take_and_throw(game, "stone_flat_1", "target_barrel")

    progression_service(db).evaluate("player_1")

    with db.connect() as connection:
        assert connection.execute(
            "SELECT 1 FROM abilities WHERE player_id = ? AND ability_id = ?",
            ("player_1", "aimed_throw"),
        ).fetchone() is None


def test_varied_competent_throwing_unlocks_achievement_and_ability(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    perform_qualifying_pattern(game)

    with db.connect() as connection:
        assert connection.execute(
            "SELECT 1 FROM achievements WHERE player_id = ? AND achievement_id = ?",
            ("player_1", "hand_remembers_arc"),
        ).fetchone() is not None
        assert connection.execute(
            "SELECT 1 FROM abilities WHERE player_id = ? AND ability_id = ?",
            ("player_1", "aimed_throw"),
        ).fetchone() is not None


def test_progression_unlock_persists_after_database_reopen(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    perform_qualifying_pattern(game)

    reopened = GameDatabase(db.path)
    with reopened.connect() as connection:
        row = connection.execute(
            "SELECT ability_id FROM abilities WHERE player_id = ? AND ability_id = ?",
            ("player_1", "aimed_throw"),
        ).fetchone()

    assert row is not None
    assert row["ability_id"] == "aimed_throw"


def test_aimed_throw_is_locked_before_progression(tmp_path: Path) -> None:
    _db, game = make_game(tmp_path)
    assert game.execute(
        CanonicalAction(actor_id="player_1", action_type=ActionType.TAKE, item_id="stone_flat_1")
    ).success

    result = game.execute(
        CanonicalAction(
            actor_id="player_1",
            action_type=ActionType.THROW,
            item_id="stone_flat_1",
            target_id="target_barrel",
            modifiers={"aimed": True},
        )
    )

    assert result.success is False
    assert result.code == "ACTION_NOT_UNLOCKED"


def test_aimed_throw_is_usable_immediately_after_progression_unlock(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    perform_qualifying_pattern(game)

    with db.connect() as connection:
        assert connection.execute(
            "SELECT 1 FROM abilities WHERE player_id = ? AND ability_id = ?",
            ("player_1", "aimed_throw"),
        ).fetchone() is not None

    result = game.execute(
        CanonicalAction(
            actor_id="player_1",
            action_type=ActionType.THROW,
            item_id="stone_flat_1",
            target_id="oren_innkeeper",
            modifiers={"aimed": True},
        )
    )

    assert result.success is True
    assert result.data["aimed"] is True
    assert result.data["accuracy_chance"] == pytest.approx(0.55)
