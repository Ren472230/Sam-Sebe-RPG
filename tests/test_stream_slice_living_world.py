from __future__ import annotations

import json

from samseberpg.db import GameDatabase
from samseberpg.living_world import LivingWorldService


def test_talen_arrives_once_at_tick_10_and_oren_requests_bread(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    service = LivingWorldService()

    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")

        before = service.advance(conn, 9)
        assert not any(event["event_type"] == "WAYFARER_ARRIVED" for event in before)
        assert conn.execute(
            "SELECT location_id FROM actors WHERE id = 'npc_wayfarer_1'"
        ).fetchone()[0] is None

        tick_10_events = service.advance(conn, 1)
        arrivals = [
            event for event in tick_10_events if event["event_type"] == "WAYFARER_ARRIVED"
        ]
        assert len(arrivals) == 1
        assert arrivals[0]["actor_id"] == "npc_wayfarer_1"
        assert arrivals[0]["location_id"] == "tavern_interior"
        assert conn.execute(
            "SELECT location_id FROM actors WHERE id = 'npc_wayfarer_1'"
        ).fetchone()[0] == "tavern_interior"

        oren_state = json.loads(
            str(
                conn.execute(
                    "SELECT state_json FROM npc_runtime_state WHERE npc_actor_id = 'npc_oren'"
                ).fetchone()[0]
            )
        )
        assert oren_state == {"bread_received": False, "bread_requested": True}
        requests = [
            event
            for event in tick_10_events
            if event["event_type"] == "NPC_REQUESTED_RESOURCE"
            and event["actor_id"] == "npc_oren"
            and event["target_id"] == "bread_loaf_1"
        ]
        assert len(requests) == 1

        later = service.advance(conn, 5)
        assert not any(event["event_type"] == "WAYFARER_ARRIVED" for event in later)
        assert not any(
            event["event_type"] == "NPC_REQUESTED_RESOURCE"
            and event["actor_id"] == "npc_oren"
            and event["target_id"] == "bread_loaf_1"
            for event in later
        )
        assert conn.execute(
            "SELECT COUNT(*) FROM world_events WHERE event_type = 'WAYFARER_ARRIVED'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM world_events "
            "WHERE event_type = 'NPC_REQUESTED_RESOURCE' "
            "AND actor_id = 'npc_oren' AND target_id = 'bread_loaf_1'"
        ).fetchone()[0] == 1
    finally:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.close()
