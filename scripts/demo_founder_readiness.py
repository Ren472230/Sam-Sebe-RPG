from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from samseberpg.cli import render_help, resolve_and_record_player_input
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def must(game: GameService, action: CanonicalAction):
    result = game.execute(action)
    if not result.success:
        raise RuntimeError(f"{action}: {result.code} {result.summary}")
    return result


def trust(db: GameDatabase, npc_id: str) -> float:
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT value FROM relations
            WHERE source_id=? AND target_id='player_1' AND relation_type='trust'
            """,
            (npc_id,),
        ).fetchone()
    return float(row["value"]) if row else 0.0


def run(db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()

    db = GameDatabase(db_path)
    db.initialize()
    db.bootstrap_if_empty()
    game = GameService(db, seed=10)

    founder_help = render_help("founder", has_aimed=False, ollama_enabled=False)
    if "дать <item_id>" in founder_help or "прицельно бросить" in founder_help:
        raise RuntimeError("Founder help leaks gameplay catalogue or locked ability")

    resolution = resolve_and_record_player_input("взять stone_flat_1", db)
    if resolution.action is None:
        raise RuntimeError("Deterministic founder smoke input was not recognized")
    first = must(game, resolution.action)
    db.complete_input_attempt(resolution.attempt_id, first.code)
    attempts = db.list_input_attempts()
    if len(attempts) != 1 or attempts[0]["result_code"] != "OK":
        raise RuntimeError("Input telemetry did not round-trip through GameService")
    print("input_telemetry=PASS")

    observed = must(
        game,
        CanonicalAction("player_1", ActionType.DROP, item_id="stone_flat_1"),
    ).data.get("observed_world_events", [])
    if [event.get("event_type") for event in observed] != ["NPC_WORKED"]:
        raise RuntimeError(f"Expected local Living World feedback, got: {observed}")
    print("observable_world=PASS")

    must(game, CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1"))
    must(
        game,
        CanonicalAction(
            "player_1",
            ActionType.GIVE,
            target_id="mira_craftswoman",
            item_id="stone_flat_1",
        ),
    )
    must(game, CanonicalAction("player_1", ActionType.TAKE, item_id="stone_round_1"))
    must(
        game,
        CanonicalAction(
            "player_1",
            ActionType.GIVE,
            target_id="mira_craftswoman",
            item_id="stone_round_1",
        ),
    )
    resources = db.fetch_player_resources("player_1")
    if resources is None or resources["coins"] != 2 or trust(db, "mira_craftswoman") != 2:
        raise RuntimeError("Audited starter balance is not active")

    must(game, CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square"))
    must(
        game,
        CanonicalAction(
            "player_1",
            ActionType.TALK,
            target_id="oren_innkeeper",
            modifiers={"topic": "request_lodging"},
        ),
    )
    resources = db.fetch_player_resources("player_1")
    if resources is None or resources != {"coins": 2, "lodging_secured": True}:
        raise RuntimeError("Two-contribution social lodging route is not reachable")
    print("social_route=PASS")

    must(game, CanonicalAction("player_1", ActionType.MOVE, destination_id="river_edge"))
    must(game, CanonicalAction("player_1", ActionType.TAKE, item_id="pinecone_1"))
    hostile = must(
        game,
        CanonicalAction(
            "player_1",
            ActionType.THROW,
            item_id="pinecone_1",
            target_id="raven_2",
        ),
    )
    raven = db.fetch_entity("raven_2")
    if (
        not hostile.data.get("hit")
        or raven is None
        or raven["state"].get("fear") != 2
        or raven["state"].get("trust") != -1
        or raven["location_id"] != "village_square"
    ):
        raise RuntimeError("Obvious hostile action did not create persistent animal consequence")
    print("hostile_consequence=PASS")

    must(game, CanonicalAction("player_1", ActionType.TAKE, item_id="pinecone_1"))
    must(game, CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square"))
    must(game, CanonicalAction("player_1", ActionType.MOVE, destination_id="workshop_yard"))
    with db.connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO abilities(player_id, ability_id, mechanic_json, unlocked_at)
            VALUES ('player_1', 'aimed_throw', ?, ?)
            """,
            (
                json.dumps(
                    {
                        "primitive": "MODIFY_ACCURACY",
                        "value": 10,
                        "action": "THROW",
                        "variant": "aimed",
                    }
                ),
                db.get_world_time(),
            ),
        )
    precision = must(
        game,
        CanonicalAction(
            "player_1",
            ActionType.THROW,
            item_id="pinecone_1",
            target_id="target_barrel",
            modifiers={"aimed": True},
        ),
    )
    barrel = db.fetch_entity("target_barrel")
    if (
        not precision.data.get("hit")
        or precision.data.get("precision_task_completed") is not True
        or barrel is None
        or barrel["state"].get("precision_fixed") is not True
    ):
        raise RuntimeError("Aimed throw still has no positive systemic use")
    print("precision_utility=PASS")

    if db.get_schema_version() != 2:
        raise RuntimeError("Founder-ready DB is not schema v2")
    print("schema_version=2")
    print("FOUNDER READINESS DEMO PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Fix Pack A founder-readiness smoke")
    parser.add_argument("--db", type=Path, default=ROOT / "founder_readiness_demo.db")
    args = parser.parse_args()
    run(args.db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
