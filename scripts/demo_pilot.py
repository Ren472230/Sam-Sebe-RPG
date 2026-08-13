from __future__ import annotations

import argparse
from pathlib import Path

from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def action(game: GameService, action_type: ActionType, **kwargs):
    result = game.execute(CanonicalAction(actor_id="player_1", action_type=action_type, **kwargs))
    if not result.success:
        raise RuntimeError(f"{action_type.value} failed: {result.code} — {result.summary}")
    unlocked = result.data.get("unlocked")
    if unlocked:
        print("UNLOCK:", ", ".join(unlocked))
    return result


def take_and_throw(game: GameService, item_id: str, target_id: str):
    action(game, ActionType.TAKE, item_id=item_id)
    return action(game, ActionType.THROW, item_id=item_id, target_id=target_id)


def run_demo(db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()

    db = GameDatabase(db_path)
    db.initialize()
    db.bootstrap_if_empty()
    game = GameService(db, seed=1)

    print("== SAM-SEBE RPG PILOT v0.1 ==")
    opening = action(game, ActionType.LOOK)
    print(opening.summary)

    for _ in range(3):
        take_and_throw(game, "stone_flat_1", "target_barrel")
        take_and_throw(game, "stone_round_1", "mira_craftswoman")

    action(game, ActionType.TAKE, item_id="stone_flat_1")
    action(game, ActionType.TAKE, item_id="stone_round_1")
    action(game, ActionType.MOVE, destination_id="village_square")

    for _ in range(3):
        action(game, ActionType.THROW, item_id="stone_flat_1", target_id="oren_innkeeper")
        action(game, ActionType.TAKE, item_id="stone_flat_1")
        action(game, ActionType.THROW, item_id="stone_round_1", target_id="oren_innkeeper")
        action(game, ActionType.TAKE, item_id="stone_round_1")

    with db.connect() as connection:
        achievements = [
            row["achievement_id"]
            for row in connection.execute(
                "SELECT achievement_id FROM achievements WHERE player_id = ? ORDER BY achievement_id",
                ("player_1",),
            ).fetchall()
        ]
        abilities = [
            row["ability_id"]
            for row in connection.execute(
                "SELECT ability_id FROM abilities WHERE player_id = ? ORDER BY ability_id",
                ("player_1",),
            ).fetchall()
        ]

    print("ACHIEVEMENTS:", ", ".join(achievements) or "none")
    print("ABILITIES:", ", ".join(abilities) or "none")

    aimed = action(
        game,
        ActionType.THROW,
        item_id="stone_flat_1",
        target_id="oren_innkeeper",
        modifiers={"aimed": True},
    )
    print(
        "AIMED THROW:",
        "hit" if aimed.data["hit"] else "miss",
        f"chance={aimed.data['accuracy_chance']:.0%}",
    )

    if "hand_remembers_arc" not in achievements or "aimed_throw" not in abilities:
        raise RuntimeError("Progression loop did not unlock expected achievement/ability")
    if not aimed.data.get("aimed") or aimed.data.get("accuracy_chance") != 0.55:
        raise RuntimeError("Aimed Throw mechanic is not active")

    print("DEMO PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the deterministic Pilot v0.1 scenario")
    parser.add_argument("--db", type=Path, default=Path("demo-pilot.db"))
    args = parser.parse_args()
    run_demo(args.db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
