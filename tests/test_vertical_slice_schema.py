from __future__ import annotations

from pathlib import Path

from samseberpg.db import GameDatabase


def test_vertical_slice_bootstrap_is_additive_and_idempotent(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    db.initialize()

    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM locations WHERE id = 'tavern_interior'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM entities WHERE entity_type = 'firewood'"
        ).fetchone()[0] == 5
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'quests'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'npc_memories'"
        ).fetchone()[0] == 1
        edges = conn.execute(
            "SELECT from_location_id, to_location_id FROM location_edges "
            "WHERE from_location_id = 'tavern_interior' OR to_location_id = 'tavern_interior'"
        ).fetchall()
        assert {tuple(row) for row in edges} == {
            ("village_square", "tavern_interior"),
            ("tavern_interior", "village_square"),
        }


def test_reinitialize_heals_legacy_oren_location_and_schedule(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE actors SET location_id = 'village_square' WHERE id = 'npc_oren'"
        )
        conn.execute(
            "UPDATE npc_schedule SET location_id = 'village_square' WHERE npc_actor_id = 'npc_oren'"
        )
        conn.execute("COMMIT")

    db.initialize()

    with db.connect() as conn:
        oren = conn.execute(
            "SELECT location_id FROM actors WHERE id = 'npc_oren'"
        ).fetchone()
        schedule_locations = {
            str(row[0])
            for row in conn.execute(
                "SELECT location_id FROM npc_schedule WHERE npc_actor_id = 'npc_oren'"
            ).fetchall()
        }

    assert oren is not None
    assert oren[0] == "tavern_interior"
    assert schedule_locations == {"tavern_interior"}
