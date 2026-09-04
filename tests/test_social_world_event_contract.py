from __future__ import annotations

from samseberpg.db import GameDatabase
from samseberpg.living_world import LivingWorldService


def test_advance_returns_persisted_world_event_id(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        events = LivingWorldService().advance(conn, 2)
        assert events
        event = events[0]
        assert isinstance(event["world_event_id"], int)
        row = conn.execute(
            "SELECT actor_id, event_type FROM world_events WHERE id = ?",
            (event["world_event_id"],),
        ).fetchone()
        assert row is not None
        assert row["actor_id"] == event["actor_id"]
        assert row["event_type"] == event["event_type"]
        conn.execute("ROLLBACK")
