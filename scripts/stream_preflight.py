from __future__ import annotations

import json
import tempfile
from pathlib import Path

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService
from samseberpg.living_world import LivingWorldService
from samseberpg.social_world import SocialWorldService

from scripts.run_stream_slice import STREAM_NOW


ROAD_FACT_KEY = "wayfarer_eastern_road_delay:v1"


def run_preflight(db_path: str | Path) -> dict[str, object]:
    path = Path(db_path)
    if path.exists():
        raise ValueError(f"preflight requires a fresh database path: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)

    db = GameDatabase(path)
    db.initialize()
    game = GameService(
        db,
        FakeClock(STREAM_NOW),
        living_world=LivingWorldService(),
        social_world=SocialWorldService(),
    )
    player_id = game.register_player("stream-preflight", "Stream Preflight")
    result = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.WAIT,
            modifiers={"ticks": 20},
        ),
        external_id="stream-preflight-wait-20",
    )
    if not result.success:
        raise RuntimeError(f"preflight WAIT failed: {result.code}: {result.summary}")

    with db.connect() as conn:
        tick = int(
            conn.execute(
                "SELECT tick FROM world_runtime WHERE world_id = 'village_1'"
            ).fetchone()[0]
        )
        wayfarer_arrivals = int(
            conn.execute(
                "SELECT COUNT(*) FROM world_events "
                "WHERE actor_id = 'npc_wayfarer_1' AND event_type = 'WAYFARER_ARRIVED'"
            ).fetchone()[0]
        )
        oren_bread_requests = int(
            conn.execute(
                "SELECT COUNT(*) FROM world_events "
                "WHERE actor_id = 'npc_oren' AND event_type = 'NPC_REQUESTED_RESOURCE' "
                "AND target_id = 'bread_loaf_1'"
            ).fetchone()[0]
        )
        road_fact_knowers = [
            str(row[0])
            for row in conn.execute(
                "SELECT knower_actor_id FROM npc_knowledge WHERE fact_key = ? "
                "ORDER BY knower_actor_id",
                (ROAD_FACT_KEY,),
            ).fetchall()
        ]
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_key_errors = len(conn.execute("PRAGMA foreign_key_check").fetchall())

    reopened = GameDatabase(path)
    reopened.initialize()
    with reopened.connect() as conn:
        reopen_tick = int(
            conn.execute(
                "SELECT tick FROM world_runtime WHERE world_id = 'village_1'"
            ).fetchone()[0]
        )

    report: dict[str, object] = {
        "tick": tick,
        "wayfarer_arrivals": wayfarer_arrivals,
        "oren_bread_requests": oren_bread_requests,
        "road_fact_knowers": road_fact_knowers,
        "integrity": integrity,
        "foreign_key_errors": foreign_key_errors,
        "reopen_tick": reopen_tick,
    }
    _validate_report(report)
    return report


def _validate_report(report: dict[str, object]) -> None:
    expected = {
        "tick": 20,
        "wayfarer_arrivals": 1,
        "oren_bread_requests": 1,
        "road_fact_knowers": ["npc_oren", "npc_wayfarer_1"],
        "integrity": "ok",
        "foreign_key_errors": 0,
        "reopen_tick": 20,
    }
    for key, value in expected.items():
        if report.get(key) != value:
            raise RuntimeError(
                f"Stream Slice preflight invariant failed for {key}: "
                f"expected {value!r}, got {report.get(key)!r}"
            )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sam-sebe-stream-preflight-") as temp_dir:
        report = run_preflight(Path(temp_dir) / "preflight.sqlite3")
    print("STREAM SLICE PREFLIGHT: PASS")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
