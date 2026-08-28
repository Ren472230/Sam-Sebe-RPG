from __future__ import annotations

import json
from pathlib import Path

from samseberpg.db import DEFAULT_WORLD_ID, GameDatabase


RUNTIME_TABLES = {"world_runtime", "npc_runtime_state", "world_events"}


def _runtime_state(conn, npc_actor_id: str) -> tuple[int, dict[str, object], int]:
    row = conn.execute(
        "SELECT override_active, state_json, updated_tick "
        "FROM npc_runtime_state WHERE npc_actor_id = ?",
        (npc_actor_id,),
    ).fetchone()
    assert row is not None
    return int(row[0]), json.loads(str(row[1])), int(row[2])


def test_clean_bootstrap_adds_runtime_tables_defaults_and_real_driftwood(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    with db.connect() as conn:
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert RUNTIME_TABLES <= tables
        assert conn.execute(
            "SELECT tick FROM world_runtime WHERE world_id = ?", (DEFAULT_WORLD_ID,)
        ).fetchone()[0] == 0

        assert _runtime_state(conn, "npc_mira") == (
            0,
            {"requested_wood": False, "wood_stock": 2, "work_cycles": 0},
            0,
        )
        assert _runtime_state(conn, "npc_kaspar") == (
            0,
            {"carrying_wood": 0, "goal": None},
            0,
        )

        driftwood = conn.execute(
            "SELECT name, entity_type, location_id, owner_actor_id, portable, state_json "
            "FROM entities WHERE id = 'driftwood_1'"
        ).fetchone()
        assert driftwood is not None
        assert tuple(driftwood[:5]) == ("Driftwood", "material", "river_edge", None, 1)
        assert json.loads(str(driftwood[5])) == {"resource_kind": "useful_wood"}


def test_initialize_migrates_existing_save_additively(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "legacy.sqlite3")
    db.initialize()

    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        created_at = "2026-08-27T12:00:00.000Z"
        conn.execute(
            "INSERT INTO actors (id, world_id, actor_type, name, location_id, created_at) "
            "VALUES ('player_legacy', ?, 'player', 'Legacy', 'workshop_yard', ?)",
            (DEFAULT_WORLD_ID, created_at),
        )
        conn.execute(
            "INSERT INTO players (actor_id, discord_user_id, joined_at, coins) "
            "VALUES ('player_legacy', 'legacy-user', ?, 17)",
            (created_at,),
        )
        conn.execute(
            "UPDATE entities SET location_id = NULL, owner_actor_id = 'player_legacy' "
            "WHERE id = 'stone_flat_1'"
        )
        conn.execute(
            "INSERT INTO relations "
            "(source_actor_id, target_actor_id, familiarity, trust, affinity, fear, conflict, romance, updated_at) "
            "VALUES ('npc_oren', 'player_legacy', 3, 9, 2, 0, 0, 0, ?)",
            (created_at,),
        )
        conn.execute(
            "INSERT INTO quests "
            "(id, world_id, player_actor_id, quest_type, giver_actor_id, status, accepted_at, completed_at) "
            "VALUES ('legacy-quest', ?, 'player_legacy', 'bring_5_firewood', 'npc_oren', 'active', ?, NULL)",
            (DEFAULT_WORLD_ID, created_at),
        )
        conn.execute(
            "INSERT INTO npc_memories "
            "(npc_actor_id, subject_actor_id, fact, importance, reinforcement_count, created_at) "
            "VALUES ('npc_oren', 'player_legacy', 'legacy fact', 70, 2, ?)",
            (created_at,),
        )
        conn.execute(
            "INSERT INTO action_events "
            "(world_id, external_id, occurred_at, actor_id, action_type, target_id, location_id, "
            "success, result_code, summary, evidence_json) "
            "VALUES (?, 'legacy-event', ?, 'player_legacy', 'LOOK', NULL, 'workshop_yard', "
            "1, 'OK', 'legacy action', '{}')",
            (DEFAULT_WORLD_ID, created_at),
        )
        conn.execute("DELETE FROM entities WHERE id = 'driftwood_1'")
        conn.execute("DROP TABLE IF EXISTS world_events")
        conn.execute("DROP TABLE IF EXISTS npc_runtime_state")
        conn.execute("DROP TABLE IF EXISTS world_runtime")
        conn.execute("COMMIT")

    db.initialize()

    with db.connect() as conn:
        assert conn.execute(
            "SELECT coins FROM players WHERE actor_id = 'player_legacy'"
        ).fetchone()[0] == 17
        assert tuple(
            conn.execute(
                "SELECT location_id, owner_actor_id FROM entities WHERE id = 'stone_flat_1'"
            ).fetchone()
        ) == (None, "player_legacy")
        assert conn.execute(
            "SELECT trust FROM relations WHERE source_actor_id = 'npc_oren' "
            "AND target_actor_id = 'player_legacy'"
        ).fetchone()[0] == 9
        assert conn.execute(
            "SELECT status FROM quests WHERE id = 'legacy-quest'"
        ).fetchone()[0] == "active"
        assert conn.execute(
            "SELECT fact FROM npc_memories WHERE npc_actor_id = 'npc_oren' "
            "AND subject_actor_id = 'player_legacy'"
        ).fetchone()[0] == "legacy fact"
        assert conn.execute(
            "SELECT summary FROM action_events WHERE external_id = 'legacy-event'"
        ).fetchone()[0] == "legacy action"
        assert conn.execute(
            "SELECT location_id FROM entities WHERE id = 'driftwood_1'"
        ).fetchone()[0] == "river_edge"
        assert conn.execute(
            "SELECT tick FROM world_runtime WHERE world_id = ?", (DEFAULT_WORLD_ID,)
        ).fetchone()[0] == 0


def test_reinitialize_preserves_runtime_state_and_does_not_respawn_consumed_driftwood(
    tmp_path: Path,
) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE world_runtime SET tick = 7 WHERE world_id = ?", (DEFAULT_WORLD_ID,)
        )
        conn.execute(
            "UPDATE npc_runtime_state SET override_active = 1, state_json = ?, updated_tick = 7 "
            "WHERE npc_actor_id = 'npc_mira'",
            (json.dumps({"wood_stock": 0, "work_cycles": 2, "requested_wood": True}),),
        )
        conn.execute(
            "UPDATE npc_runtime_state SET override_active = 1, state_json = ?, updated_tick = 7 "
            "WHERE npc_actor_id = 'npc_kaspar'",
            (json.dumps({"carrying_wood": 1, "goal": "deliver_wood"}),),
        )
        conn.execute(
            "UPDATE entities SET location_id = NULL, owner_actor_id = NULL "
            "WHERE id = 'driftwood_1'"
        )
        conn.execute("COMMIT")

    db.initialize()

    with db.connect() as conn:
        assert conn.execute(
            "SELECT tick FROM world_runtime WHERE world_id = ?", (DEFAULT_WORLD_ID,)
        ).fetchone()[0] == 7
        assert _runtime_state(conn, "npc_mira") == (
            1,
            {"wood_stock": 0, "work_cycles": 2, "requested_wood": True},
            7,
        )
        assert _runtime_state(conn, "npc_kaspar") == (
            1,
            {"carrying_wood": 1, "goal": "deliver_wood"},
            7,
        )
        driftwood = conn.execute(
            "SELECT location_id, owner_actor_id FROM entities WHERE id = 'driftwood_1'"
        ).fetchone()
        assert tuple(driftwood) == (None, None)
