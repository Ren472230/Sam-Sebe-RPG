from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


PLAYER = "player_1"


def ensure_owned(db: GameDatabase, game: GameService, item_id: str) -> None:
    if item_id in db.list_inventory(PLAYER):
        return
    result = game.execute(CanonicalAction(PLAYER, ActionType.TAKE, item_id=item_id))
    if not result.success:
        raise RuntimeError(result.summary)


def throw_once(
    db: GameDatabase, game: GameService, item_id: str, target_id: str
) -> None:
    ensure_owned(db, game, item_id)
    result = game.execute(
        CanonicalAction(
            PLAYER,
            ActionType.THROW,
            item_id=item_id,
            target_id=target_id,
        )
    )
    if not result.success:
        raise RuntimeError(result.summary)
    print(
        f"throw {item_id} -> {target_id}: "
        f"{'hit' if result.data['hit'] else 'miss'} ({result.data['accuracy']:.0%})"
    )


def move_with_projectiles(
    db: GameDatabase, game: GameService, destination_id: str
) -> None:
    ensure_owned(db, game, "stone_flat_1")
    ensure_owned(db, game, "stone_round_1")
    result = game.execute(
        CanonicalAction(PLAYER, ActionType.MOVE, destination_id=destination_id)
    )
    if not result.success:
        raise RuntimeError(result.summary)


def run_demo(db_path: Path) -> None:
    db = GameDatabase(db_path)
    db.initialize()
    db.bootstrap_if_empty()
    game = GameService(db, seed=1)

    print("=== Sam-Sebe-RPG Pilot v0.1 deterministic demo ===")

    for item_id in ["stone_flat_1", "stone_round_1"] * 2:
        throw_once(db, game, item_id, "target_barrel")

    move_with_projectiles(db, game, "village_square")
    for item_id in ["stone_flat_1", "stone_round_1"] * 2:
        throw_once(db, game, item_id, "target_sign")

    move_with_projectiles(db, game, "river_edge")
    for item_id in ["stone_flat_1", "stone_round_1"] * 2:
        throw_once(db, game, item_id, "target_post")

    profile = db.fetch_behavior_profile(PLAYER, "throwing")
    print(f"behavior_profile: {profile}")

    if not db.has_achievement(PLAYER, "hand_remembers_arc"):
        raise RuntimeError("achievement did not unlock")
    if not db.has_ability(PLAYER, "aimed_throw"):
        raise RuntimeError("aimed_throw did not unlock")

    print("achievement hand_remembers_arc: unlocked")
    print("aimed_throw: unlocked")

    ensure_owned(db, game, "stone_flat_1")
    aimed = game.execute(
        CanonicalAction(
            PLAYER,
            ActionType.THROW,
            item_id="stone_flat_1",
            target_id="target_post",
            modifiers={"aimed": True},
        )
    )
    if not aimed.success:
        raise RuntimeError(aimed.summary)
    print(f"aimed_accuracy: {aimed.data['accuracy']:.0%}")

    reopened = GameDatabase(db_path)
    if not reopened.has_ability(PLAYER, "aimed_throw"):
        raise RuntimeError("ability did not survive database reopen")

    print("persistence: PASS")
    print("DEMO PASS")


def main() -> int:
    with TemporaryDirectory(prefix="sam_sebe_rpg_demo_") as temp_dir:
        run_demo(Path(temp_dir) / "demo.db")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
