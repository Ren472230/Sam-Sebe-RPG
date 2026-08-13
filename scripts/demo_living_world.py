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
    game = GameService(db, seed=1)

    # No social command causes this chain: time alone lets NPC needs resolve.
    must(game, CanonicalAction("player_1", ActionType.LOOK))
    must(game, CanonicalAction("player_1", ActionType.WAIT, modifiers={"ticks": 7}))

    kaspar_before = db.fetch_entity("kaspar_forager")
    if kaspar_before is None or kaspar_before["state"].get("carrying_wood") != 1:
        raise RuntimeError("Kaspar did not preserve the wood in transit before reopen")

    # Reopen at the most interesting point: Kaspar is carrying wood at Mira's yard.
    reopened = GameDatabase(db_path)
    reopened.initialize()
    reopened.bootstrap_if_empty()
    restarted_game = GameService(reopened, seed=999)
    must(
        restarted_game,
        CanonicalAction("player_1", ActionType.WAIT, modifiers={"ticks": 1}),
    )

    events = reopened.list_world_events()
    for event in events:
        print(
            f"t={event['world_time']} {event['actor_id']} "
            f"{event['event_type']} — {event['summary']}"
        )

    event_types = [event["event_type"] for event in events]
    required = {
        "NPC_WORKED",
        "NPC_REQUESTED_RESOURCE",
        "NPC_COLLECTED_RESOURCE",
        "NPC_MOVED",
        "NPC_DELIVERED_RESOURCE",
    }
    if not required <= set(event_types):
        raise RuntimeError(f"Missing autonomous events: {sorted(required - set(event_types))}")

    mira = reopened.fetch_entity("mira_craftswoman")
    kaspar = reopened.fetch_entity("kaspar_forager")
    if mira is None or kaspar is None:
        raise RuntimeError("Living World NPC state missing after reopen")
    if mira["state"].get("wood_stock") != 1:
        raise RuntimeError("Mira did not receive wood")
    if mira["state"].get("requested_wood") is not False:
        raise RuntimeError("Mira request did not clear")
    if kaspar["state"].get("carrying_wood") != 0:
        raise RuntimeError("Kaspar still carries delivered wood")

    print("persistence: PASS")
    print("LIVING WORLD DEMO PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic Living World v0 demo")
    parser.add_argument("--db", type=Path, default=ROOT / "living_world_demo.db")
    args = parser.parse_args()
    run(args.db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
