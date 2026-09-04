from __future__ import annotations

from pathlib import Path

from samseberpg.db import GameDatabase


EXPECTED_TABLES = {
    "worlds",
    "locations",
    "location_edges",
    "actors",
    "players",
    "npcs",
    "npc_schedule",
    "entities",
    "relations",
    "action_events",
    "processed_interactions",
    "quests",
    "npc_memories",
    "dialogue_turns",
}


def test_initialize_bootstraps_one_shared_village_idempotently(tmp_path: Path) -> None:
    db_path = tmp_path / "world.sqlite3"
    db = GameDatabase(db_path)

    db.initialize()
    db.initialize()

    with db.connect() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert EXPECTED_TABLES <= tables

        assert conn.execute("SELECT COUNT(*) FROM worlds").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0] == 4
        assert conn.execute("SELECT COUNT(*) FROM npcs").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0] >= 10

        stone = conn.execute(
            "SELECT location_id, owner_actor_id, portable "
            "FROM entities WHERE id = ?",
            ("stone_flat_1",),
        ).fetchone()
        assert stone is not None
        assert stone[0] == "workshop_yard"
        assert stone[1] is None
        assert stone[2] == 1


def test_bootstrap_contains_required_npcs_and_locations(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    with db.connect() as conn:
        location_ids = {
            row[0] for row in conn.execute("SELECT id FROM locations").fetchall()
        }
        assert location_ids == {
            "workshop_yard",
            "village_square",
            "river_edge",
            "tavern_interior",
        }

        npcs = {
            row[0]: (row[1], row[2])
            for row in conn.execute(
                "SELECT npcs.actor_id, actors.name, npcs.role "
                "FROM npcs JOIN actors ON actors.id = npcs.actor_id"
            ).fetchall()
        }
        assert npcs == {
            "npc_mira": ("Mira", "craftswoman"),
            "npc_oren": ("Oren", "innkeeper"),
            "npc_kaspar": ("Kaspar", "forager"),
        }


def test_dialogue_turns_schema_exists(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    with db.connect() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(dialogue_turns)")}

    assert {
        "npc_actor_id",
        "player_actor_id",
        "user_text",
        "npc_text",
        "proposal_json",
        "used_fallback",
        "created_at",
    } <= columns
