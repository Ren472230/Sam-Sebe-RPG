from __future__ import annotations

import importlib
import json

from samseberpg.db import DEFAULT_WORLD_ID, GameDatabase


def _service_class():
    return importlib.import_module("samseberpg.social_world").SocialWorldService


def _persist_delivery_event(db: GameDatabase) -> dict[str, object]:
    with db.connect() as conn:
        tick = 8
        cursor = conn.execute(
            "INSERT INTO world_events "
            "(world_id, tick, actor_id, event_type, target_id, location_id, data_json, summary) "
            "VALUES (?, ?, 'npc_kaspar', 'NPC_DELIVERED_RESOURCE', 'npc_mira', "
            "'workshop_yard', ?, ?)",
            (
                DEFAULT_WORLD_ID,
                tick,
                json.dumps(
                    {"amount": 1, "resource_kind": "useful_wood"},
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                "Kaspar delivered one unit of useful wood to Mira.",
            ),
        )
        event_id = int(cursor.lastrowid)
    return {
        "id": event_id,
        "world_event_id": event_id,
        "world_id": DEFAULT_WORLD_ID,
        "tick": tick,
        "actor_id": "npc_kaspar",
        "event_type": "NPC_DELIVERED_RESOURCE",
        "target_id": "npc_mira",
        "location_id": "workshop_yard",
        "data": {"amount": 1, "resource_kind": "useful_wood"},
        "summary": "Kaspar delivered one unit of useful wood to Mira.",
    }


def test_kaspar_delivery_teaches_mira_and_improves_relation(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    event = _persist_delivery_event(db)
    service = _service_class()()

    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        effects = service.process_world_events(conn, [event])
        knowledge = conn.execute(
            "SELECT fact_key, fact_text, source_kind, source_actor_id, "
            "source_world_event_id, confidence, shareable, learned_tick "
            "FROM npc_knowledge WHERE knower_actor_id = 'npc_mira'"
        ).fetchone()
        relation = conn.execute(
            "SELECT familiarity, trust, affinity, fear, conflict, romance "
            "FROM relations WHERE source_actor_id = 'npc_mira' "
            "AND target_actor_id = 'npc_kaspar'"
        ).fetchone()

        assert len(effects) == 1
        assert knowledge is not None
        assert knowledge["fact_key"] == (
            f"kaspar_delivered_useful_wood_to_mira:{event['world_event_id']}"
        )
        assert "Kaspar personally delivered useful wood" in knowledge["fact_text"]
        assert knowledge["source_kind"] == "direct_event"
        assert knowledge["source_actor_id"] == "npc_kaspar"
        assert int(knowledge["source_world_event_id"]) == event["world_event_id"]
        assert int(knowledge["confidence"]) == 100
        assert int(knowledge["shareable"]) == 1
        assert int(knowledge["learned_tick"]) == event["tick"]
        assert relation is not None
        assert tuple(int(value) for value in relation) == (5, 5, 0, 0, 0, 0)
        conn.execute("ROLLBACK")


def test_processing_same_delivery_twice_is_idempotent(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    event = _persist_delivery_event(db)
    service = _service_class()()

    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        first = service.process_world_events(conn, [event])
        second = service.process_world_events(conn, [event])
        relation = conn.execute(
            "SELECT familiarity, trust FROM relations "
            "WHERE source_actor_id = 'npc_mira' AND target_actor_id = 'npc_kaspar'"
        ).fetchone()
        knowledge_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM npc_knowledge "
                "WHERE knower_actor_id = 'npc_mira' AND fact_key = ?",
                (f"kaspar_delivered_useful_wood_to_mira:{event['world_event_id']}",),
            ).fetchone()[0]
        )
        receipt_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM social_processed_events WHERE world_event_id = ?",
                (event["world_event_id"],),
            ).fetchone()[0]
        )

        assert len(first) == 1
        assert second == []
        assert relation is not None
        assert tuple(int(value) for value in relation) == (5, 5)
        assert knowledge_count == 1
        assert receipt_count == 1
        conn.execute("ROLLBACK")


def test_unsupported_or_malformed_events_do_not_create_social_state(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    service = _service_class()()

    unsupported = {
        "world_event_id": 999,
        "tick": 1,
        "actor_id": "npc_mira",
        "event_type": "NPC_WORKED",
        "target_id": None,
        "data": {"work_cycles": 1},
    }
    malformed = {
        "world_event_id": "not-an-int",
        "event_type": "NPC_DELIVERED_RESOURCE",
        "actor_id": "npc_kaspar",
        "target_id": "npc_mira",
        "data": {"resource_kind": "useful_wood"},
    }

    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        effects = service.process_world_events(conn, [unsupported, malformed])
        knowledge = int(conn.execute("SELECT COUNT(*) FROM npc_knowledge").fetchone()[0])
        relations = int(
            conn.execute(
                "SELECT COUNT(*) FROM relations WHERE source_actor_id = 'npc_mira' "
                "AND target_actor_id = 'npc_kaspar'"
            ).fetchone()[0]
        )
        receipts = int(
            conn.execute("SELECT COUNT(*) FROM social_processed_events").fetchone()[0]
        )
        assert effects == []
        assert knowledge == 0
        assert relations == 0
        assert receipts == 0
        conn.execute("ROLLBACK")
