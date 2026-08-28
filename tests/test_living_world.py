from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def _service():
    from samseberpg.living_world import LivingWorldService

    return LivingWorldService()


def _advance(db: GameDatabase, ticks: int) -> list[dict[str, object]]:
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            events = _service().advance(conn, ticks)
        except Exception:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
        return events


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


@pytest.mark.parametrize("ticks", [0, -1, 61, 1.5, True, None])
def test_advance_rejects_invalid_tick_counts_without_mutation(
    tmp_path: Path, ticks: object
) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError):
            _service().advance(conn, ticks)  # type: ignore[arg-type]
        conn.execute("ROLLBACK")

    with db.connect() as conn:
        assert conn.execute(
            "SELECT tick FROM world_runtime WHERE world_id = ?", (DEFAULT_WORLD_ID,)
        ).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM world_events").fetchone()[0] == 0
        assert _runtime_state(conn, "npc_mira")[1] == {
            "requested_wood": False,
            "wood_stock": 2,
            "work_cycles": 0,
        }


def test_mira_works_twice_then_requests_resource_exactly_once(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    _advance(db, 4)
    with db.connect() as conn:
        assert _runtime_state(conn, "npc_mira") == (
            0,
            {"requested_wood": False, "wood_stock": 0, "work_cycles": 2},
            4,
        )
        worked = conn.execute(
            "SELECT tick, event_type FROM world_events "
            "WHERE actor_id = 'npc_mira' ORDER BY id"
        ).fetchall()
        assert [tuple(row) for row in worked] == [
            (2, "NPC_WORKED"),
            (4, "NPC_WORKED"),
        ]

    _advance(db, 3)
    with db.connect() as conn:
        mira_override, mira_state, _ = _runtime_state(conn, "npc_mira")
        assert mira_override == 1
        assert mira_state == {
            "requested_wood": True,
            "wood_stock": 0,
            "work_cycles": 2,
        }
        requests = conn.execute(
            "SELECT tick FROM world_events "
            "WHERE actor_id = 'npc_mira' AND event_type = 'NPC_REQUESTED_RESOURCE'"
        ).fetchall()
        assert [row[0] for row in requests] == [5]
        assert conn.execute(
            "SELECT location_id FROM actors WHERE id = 'npc_mira'"
        ).fetchone()[0] == "workshop_yard"


def test_kaspar_collects_real_driftwood_moves_by_edges_and_delivers(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    returned = _advance(db, 8)

    with db.connect() as conn:
        assert [str(event["event_type"]) for event in returned] == [
            "NPC_WORKED",
            "NPC_WORKED",
            "NPC_REQUESTED_RESOURCE",
            "NPC_COLLECTED_RESOURCE",
            "NPC_MOVED",
            "NPC_MOVED",
            "NPC_DELIVERED_RESOURCE",
        ]
        moves = conn.execute(
            "SELECT tick, location_id, data_json FROM world_events "
            "WHERE actor_id = 'npc_kaspar' AND event_type = 'NPC_MOVED' ORDER BY id"
        ).fetchall()
        assert len(moves) == 2
        for row in moves:
            data = json.loads(str(row[2]))
            assert conn.execute(
                "SELECT 1 FROM location_edges WHERE from_location_id = ? AND to_location_id = ?",
                (data["from"], data["to"]),
            ).fetchone() is not None
            assert row[1] == data["to"]

        collected = conn.execute(
            "SELECT tick, target_id, location_id FROM world_events "
            "WHERE event_type = 'NPC_COLLECTED_RESOURCE'"
        ).fetchone()
        assert tuple(collected) == (5, "driftwood_1", "river_edge")
        delivered = conn.execute(
            "SELECT tick, target_id, location_id FROM world_events "
            "WHERE event_type = 'NPC_DELIVERED_RESOURCE'"
        ).fetchone()
        assert tuple(delivered) == (8, "npc_mira", "workshop_yard")

        assert _runtime_state(conn, "npc_mira") == (
            0,
            {"requested_wood": False, "wood_stock": 1, "work_cycles": 2},
            8,
        )
        assert _runtime_state(conn, "npc_kaspar") == (
            0,
            {"carrying_wood": 0, "goal": None},
            8,
        )
        assert tuple(
            conn.execute(
                "SELECT location_id, owner_actor_id FROM entities WHERE id = 'driftwood_1'"
            ).fetchone()
        ) == (None, None)
        assert conn.execute(
            "SELECT location_id FROM actors WHERE id = 'npc_kaspar'"
        ).fetchone()[0] == "workshop_yard"


def test_missing_driftwood_blocks_kaspar_without_fabrication(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    with db.connect() as conn:
        conn.execute("DELETE FROM entities WHERE id = 'driftwood_1'")

    _advance(db, 8)

    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM entities WHERE id = 'driftwood_1'"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM world_events "
            "WHERE event_type IN ('NPC_COLLECTED_RESOURCE', 'NPC_DELIVERED_RESOURCE')"
        ).fetchone()[0] == 0
        assert _runtime_state(conn, "npc_mira")[1]["requested_wood"] is True
        kaspar_override, kaspar_state, _ = _runtime_state(conn, "npc_kaspar")
        assert kaspar_override == 1
        assert kaspar_state == {"carrying_wood": 0, "goal": "collect_wood"}
        assert conn.execute(
            "SELECT location_id FROM actors WHERE id = 'npc_kaspar'"
        ).fetchone()[0] == "river_edge"


def test_player_owned_driftwood_is_not_stolen_or_recreated(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    created_at = "2026-08-27T12:00:00.000Z"
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO actors (id, world_id, actor_type, name, location_id, created_at) "
            "VALUES ('player_owner', ?, 'player', 'Owner', 'river_edge', ?)",
            (DEFAULT_WORLD_ID, created_at),
        )
        conn.execute(
            "INSERT INTO players (actor_id, discord_user_id, joined_at, coins) "
            "VALUES ('player_owner', 'owner-user', ?, 10)",
            (created_at,),
        )
        conn.execute(
            "UPDATE entities SET location_id = NULL, owner_actor_id = 'player_owner' "
            "WHERE id = 'driftwood_1'"
        )
        conn.execute("COMMIT")

    _advance(db, 8)

    with db.connect() as conn:
        assert tuple(
            conn.execute(
                "SELECT location_id, owner_actor_id FROM entities WHERE id = 'driftwood_1'"
            ).fetchone()
        ) == (None, "player_owner")
        assert conn.execute(
            "SELECT COUNT(*) FROM world_events "
            "WHERE event_type IN ('NPC_COLLECTED_RESOURCE', 'NPC_DELIVERED_RESOURCE')"
        ).fetchone()[0] == 0
        assert _runtime_state(conn, "npc_kaspar")[1] == {
            "carrying_wood": 0,
            "goal": "collect_wood",
        }


def test_close_reopen_mid_chain_preserves_state_and_continues(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    _advance(db, 6)

    with db.connect() as conn:
        assert conn.execute(
            "SELECT tick FROM world_runtime WHERE world_id = ?", (DEFAULT_WORLD_ID,)
        ).fetchone()[0] == 6
        assert _runtime_state(conn, "npc_kaspar") == (
            1,
            {"carrying_wood": 1, "goal": "deliver_wood"},
            6,
        )
        assert conn.execute(
            "SELECT location_id FROM actors WHERE id = 'npc_kaspar'"
        ).fetchone()[0] == "village_square"

    db.initialize()
    _advance(db, 2)

    with db.connect() as conn:
        assert conn.execute(
            "SELECT tick FROM world_runtime WHERE world_id = ?", (DEFAULT_WORLD_ID,)
        ).fetchone()[0] == 8
        assert _runtime_state(conn, "npc_mira")[1] == {
            "requested_wood": False,
            "wood_stock": 1,
            "work_cycles": 2,
        }
        assert _runtime_state(conn, "npc_kaspar")[1] == {
            "carrying_wood": 0,
            "goal": None,
        }
        assert conn.execute(
            "SELECT COUNT(*) FROM world_events WHERE event_type = 'NPC_DELIVERED_RESOURCE'"
        ).fetchone()[0] == 1


def test_world_events_persist_separately_from_player_action_events(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    _advance(db, 8)

    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM world_events").fetchone()[0] == 7
        assert conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0] == 0
        assert conn.execute(
            "SELECT GROUP_CONCAT(event_type, ',') FROM world_events ORDER BY id"
        ).fetchone()[0] is not None

    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM world_events").fetchone()[0] == 7
        assert conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0] == 0


def test_advance_stays_inside_callers_transaction_and_rolls_back_atomically(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _service().advance(conn, 5)
        assert conn.in_transaction is True
        assert conn.execute(
            "SELECT tick FROM world_runtime WHERE world_id = ?", (DEFAULT_WORLD_ID,)
        ).fetchone()[0] == 5
        conn.execute("ROLLBACK")

    with db.connect() as conn:
        assert conn.execute(
            "SELECT tick FROM world_runtime WHERE world_id = ?", (DEFAULT_WORLD_ID,)
        ).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM world_events").fetchone()[0] == 0
        assert _runtime_state(conn, "npc_mira")[1] == {
            "requested_wood": False,
            "wood_stock": 2,
            "work_cycles": 0,
        }
        assert tuple(
            conn.execute(
                "SELECT location_id, owner_actor_id FROM entities WHERE id = 'driftwood_1'"
            ).fetchone()
        ) == ("river_edge", None)


def test_each_npc_performs_at_most_one_autonomous_action_per_tick(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    _advance(db, 8)

    with db.connect() as conn:
        duplicates = conn.execute(
            "SELECT tick, actor_id, COUNT(*) FROM world_events "
            "GROUP BY tick, actor_id HAVING COUNT(*) > 1"
        ).fetchall()
        assert duplicates == []


def test_sqlite_integrity_and_foreign_keys_after_reopen_chain(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    _advance(db, 6)
    db.initialize()
    _advance(db, 2)

    with db.connect() as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
