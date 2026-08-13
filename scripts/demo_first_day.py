from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def must(game: GameService, action: CanonicalAction):
    result = game.execute(action)
    if not result.success:
        raise RuntimeError(f"{action}: {result.code} {result.summary}")
    return result


def run(db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()
    db = GameDatabase(db_path)
    db.initialize()
    db.bootstrap_if_empty()
    game = GameService(db, seed=4)

    # One possible first-day route, not a prescribed quest solution.
    for item_id in ("stone_flat_1", "stone_round_1"):
        must(game, CanonicalAction("player_1", ActionType.TAKE, item_id=item_id))
        must(
            game,
            CanonicalAction(
                "player_1", ActionType.GIVE, target_id="mira_craftswoman", item_id=item_id
            ),
        )

    must(game, CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square"))
    must(game, CanonicalAction("player_1", ActionType.TAKE, item_id="bread_1"))
    must(
        game,
        CanonicalAction("player_1", ActionType.FEED, target_id="raven_1", item_id="bread_1"),
    )
    must(
        game,
        CanonicalAction(
            "player_1", ActionType.TALK, target_id="oren_innkeeper", modifiers={"topic": "lodging"}
        ),
    )
    must(
        game,
        CanonicalAction(
            "player_1", ActionType.TALK, target_id="oren_innkeeper", modifiers={"topic": "pay_lodging"}
        ),
    )

    resources = db.fetch_player_resources("player_1")
    raven = db.fetch_entity("raven_1")
    print(f"world_time={db.get_world_time()}")
    print(f"coins={resources['coins']}")
    print(f"lodging_secured={resources['lodging_secured']}")
    print(f"raven_trust={raven['state']['trust']}")
    if not resources["lodging_secured"] or raven["state"]["trust"] != 1:
        raise RuntimeError("First-day demo invariant failed")
    print("FIRST DAY DEMO PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=ROOT / "first_day_demo.db")
    args = parser.parse_args()
    run(args.db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
