from __future__ import annotations

from pathlib import Path

from samseberpg.db import GameDatabase


def test_reinitialize_does_not_respawn_deleted_driftwood_after_bootstrap(
    tmp_path: Path,
) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    with db.connect() as conn:
        conn.execute("DELETE FROM entities WHERE id = 'driftwood_1'")
        assert conn.execute(
            "SELECT 1 FROM entities WHERE id = 'driftwood_1'"
        ).fetchone() is None

    db.initialize()

    with db.connect() as conn:
        assert conn.execute(
            "SELECT 1 FROM entities WHERE id = 'driftwood_1'"
        ).fetchone() is None
