import sqlite3

import pytest

from samseberpg.db import GameDatabase, SCHEMA_VERSION, UnsupportedSchemaVersionError


def test_fresh_database_initializes_to_current_schema_version(tmp_path):
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    with db.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_database_from_future_version_is_rejected(tmp_path):
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version = 999")

    db = GameDatabase(path)
    with pytest.raises(UnsupportedSchemaVersionError, match="999"):
        db.initialize()


def create_legacy_database(path):
    import json
    from samseberpg.db import SCHEMA

    legacy_schema = SCHEMA.replace(
        ",\n    coins INTEGER NOT NULL DEFAULT 0 CHECK(coins >= 0)\n);\n\nCREATE TABLE IF NOT EXISTS npc_schedule",
        "\n);\n\nCREATE TABLE IF NOT EXISTS npc_schedule",
        1,
    )
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(legacy_schema)
        conn.execute(
            "INSERT INTO worlds VALUES (?, ?, ?, ?, ?)",
            ("village_1", "Legacy Village", "UTC", "2026-08-14T08:00:00+00:00", "2026-08-14T08:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO locations VALUES (?, ?, ?, ?, ?)",
            ("village_square", "village_1", "Legacy Square", "Still here", 1),
        )
        conn.execute(
            "INSERT INTO actors VALUES (?, ?, ?, ?, ?, ?)",
            ("npc_oren", "village_1", "npc", "Oren Legacy", "village_square", "2026-08-14T08:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO npcs(actor_id, role, current_activity) VALUES (?, ?, ?)",
            ("npc_oren", "innkeeper", "waiting"),
        )
        conn.execute(
            "INSERT INTO actors VALUES (?, ?, ?, ?, ?, ?)",
            ("player_legacy", "village_1", "player", "Legacy Player", "village_square", "2026-08-14T08:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO players(actor_id, discord_user_id, joined_at, coins) VALUES (?, ?, ?, ?)",
            ("player_legacy", "legacy-discord", "2026-08-14T08:00:00+00:00", 9),
        )
        entities = [
            ("stone_flat_1", "Legacy stone", "stone", {"legacy": True}),
            ("stone_round_1", "Legacy round stone", "stone", {}),
            ("bottle_1", "Legacy bottle", "container", {"filled_with": "tea"}),
            ("village_well", "Legacy well", "fixture", {"legacy_marker": 7}),
            ("tavern_sign", "Legacy sign", "fixture", {"condition": 63}),
        ]
        for entity_id, name, entity_type, state in entities:
            conn.execute(
                """
                INSERT INTO entities(
                    id, world_id, name, entity_type, location_id, owner_actor_id,
                    portable, state_json, created_at
                ) VALUES (?, 'village_1', ?, ?, 'village_square', NULL, ?, ?, ?)
                """,
                (
                    entity_id,
                    name,
                    entity_type,
                    0 if entity_type == "fixture" else 1,
                    json.dumps(state),
                    "2026-08-14T08:00:00+00:00",
                ),
            )
        conn.execute(
            """
            INSERT INTO action_events(
                world_id, occurred_at, actor_id, action_type, success,
                result_code, summary, evidence_json
            ) VALUES ('village_1', ?, 'player_legacy', 'LOOK', 1, 'OK', 'legacy event', '{}')
            """,
            ("2026-08-14T08:01:00+00:00",),
        )
        conn.execute("PRAGMA user_version = 0")
        conn.commit()


def test_legacy_database_gets_npc_currency_without_losing_world_state(tmp_path):
    path = tmp_path / "legacy.db"
    create_legacy_database(path)
    db = GameDatabase(path)

    db.initialize()

    with db.connect() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(npcs)")}
        assert "coins" in columns
        assert conn.execute(
            "SELECT coins FROM npcs WHERE actor_id = 'npc_oren'"
        ).fetchone()[0] == 20
        assert conn.execute(
            "SELECT coins FROM players WHERE actor_id = 'player_legacy'"
        ).fetchone()[0] == 9
        assert conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0] == 1

        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE npcs SET coins = 17 WHERE actor_id = 'npc_oren'")
        conn.commit()

    db.initialize()
    with db.connect() as conn:
        assert conn.execute(
            "SELECT coins FROM npcs WHERE actor_id = 'npc_oren'"
        ).fetchone()[0] == 17


def test_legacy_entity_affordances_are_merged_without_resetting_existing_state(tmp_path):
    import json

    path = tmp_path / "legacy-data.db"
    create_legacy_database(path)
    db = GameDatabase(path)

    db.initialize()

    with db.connect() as conn:
        def state(entity_id):
            return json.loads(
                conn.execute(
                    "SELECT state_json FROM entities WHERE id = ?", (entity_id,)
                ).fetchone()[0]
            )

        flat = state("stone_flat_1")
        round_stone = state("stone_round_1")
        bottle = state("bottle_1")
        well = state("village_well")
        sign = state("tavern_sign")

    assert flat["legacy"] is True
    assert flat["throwable"] is True
    assert flat["impact_damage"] == 20
    assert round_stone["throwable"] is True
    assert round_stone["impact_damage"] == 20
    assert bottle["price"] == 3
    assert bottle["for_sale_by"] == "npc_oren"
    assert bottle["fillable"] is True
    assert bottle["filled_with"] == "tea"
    assert well["legacy_marker"] == 7
    assert well["water_source"] is True
    assert sign["condition"] == 63


def test_migration_keeps_existing_affordance_values_when_already_present(tmp_path):
    import json

    path = tmp_path / "legacy-custom.db"
    create_legacy_database(path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE entities SET state_json = ? WHERE id = 'stone_flat_1'",
            (json.dumps({"throwable": False, "impact_damage": 7}),),
        )
        conn.execute("PRAGMA user_version = 0")
        conn.commit()

    GameDatabase(path).initialize()
    with sqlite3.connect(path) as conn:
        state = json.loads(
            conn.execute(
                "SELECT state_json FROM entities WHERE id = 'stone_flat_1'"
            ).fetchone()[0]
        )
    assert state["throwable"] is False
    assert state["impact_damage"] == 7
