from datetime import datetime, timezone

from samseberpg.db import GameDatabase


def test_bootstrap_is_idempotent_and_enables_foreign_keys(tmp_path):
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty(now)
    db.bootstrap_if_empty(now)

    with db.connect() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM worlds").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM npcs").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0] >= 10
        stone = conn.execute(
            "SELECT location_id, owner_actor_id FROM entities WHERE id = ?",
            ("stone_flat_1",),
        ).fetchone()
        assert tuple(stone) == ("workshop_yard", None)
