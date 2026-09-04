from __future__ import annotations

import json

from samseberpg.db import DEFAULT_WORLD_ID, GameDatabase
from samseberpg.social_world import SocialWorldService


def _insert_player_and_commitment(db: GameDatabase) -> tuple[str, str, int]:
    player_id = "player_social_report"
    fact_key = f"player_promised_mira_useful_wood:{player_id}"
    now = "2026-09-04T17:00:00.000Z"
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO actors (id, world_id, actor_type, name, location_id, created_at) "
            "VALUES (?, ?, 'player', 'Ren', 'workshop_yard', ?)",
            (player_id, DEFAULT_WORLD_ID, now),
        )
        conn.execute(
            "INSERT INTO players (actor_id, discord_user_id, joined_at, coins) "
            "VALUES (?, 'social-report-player', ?, 10)",
            (player_id, now),
        )
        cursor = conn.execute(
            "INSERT INTO npc_knowledge "
            "(world_id, knower_actor_id, subject_actor_id, fact_key, fact_text, source_kind, "
            "source_actor_id, confidence, shareable, learned_tick, created_at) "
            "VALUES (?, 'npc_mira', ?, ?, ?, 'player_dialogue', ?, 100, 1, 5, ?)",
            (
                DEFAULT_WORLD_ID,
                player_id,
                fact_key,
                "The player promised Mira to bring useful wood while her workshop was blocked.",
                player_id,
                now,
            ),
        )
        return player_id, fact_key, int(cursor.lastrowid)


def _persist_delivery(db: GameDatabase) -> dict[str, object]:
    with db.connect() as conn:
        data = {"amount": 1, "resource_kind": "useful_wood"}
        cursor = conn.execute(
            "INSERT INTO world_events "
            "(world_id, tick, actor_id, event_type, target_id, location_id, data_json, summary) "
            "VALUES (?, 9, 'npc_kaspar', 'NPC_DELIVERED_RESOURCE', 'npc_mira', "
            "'workshop_yard', ?, 'Kaspar delivered useful wood to Mira.')",
            (
                DEFAULT_WORLD_ID,
                json.dumps(data, separators=(",", ":"), sort_keys=True),
            ),
        )
        event_id = int(cursor.lastrowid)
    return {
        "id": event_id,
        "world_event_id": event_id,
        "world_id": DEFAULT_WORLD_ID,
        "tick": 9,
        "actor_id": "npc_kaspar",
        "event_type": "NPC_DELIVERED_RESOURCE",
        "target_id": "npc_mira",
        "location_id": "workshop_yard",
        "data": {"amount": 1, "resource_kind": "useful_wood"},
        "summary": "Kaspar delivered useful wood to Mira.",
    }


def test_delivery_contact_propagates_miras_shareable_commitment_to_kaspar(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    player_id, fact_key, mira_knowledge_id = _insert_player_and_commitment(db)
    event = _persist_delivery(db)

    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        SocialWorldService().process_world_events(conn, [event])
        row = conn.execute(
            "SELECT subject_actor_id, fact_text, source_kind, source_actor_id, "
            "source_knowledge_id, confidence, shareable, learned_tick "
            "FROM npc_knowledge WHERE knower_actor_id = 'npc_kaspar' AND fact_key = ?",
            (fact_key,),
        ).fetchone()
        oren_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM npc_knowledge "
                "WHERE knower_actor_id = 'npc_oren' AND fact_key = ?",
                (fact_key,),
            ).fetchone()[0]
        )
        assert row is not None
        assert row["subject_actor_id"] == player_id
        assert "Mira said" in row["fact_text"]
        assert row["source_kind"] == "npc_report"
        assert row["source_actor_id"] == "npc_mira"
        assert int(row["source_knowledge_id"]) == mira_knowledge_id
        assert int(row["confidence"]) == 90
        assert int(row["shareable"]) == 0
        assert int(row["learned_tick"]) == event["tick"]
        assert oren_count == 0
        conn.execute("ROLLBACK")


def test_delivery_without_mira_commitment_does_not_fabricate_player_report(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    event = _persist_delivery(db)

    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        SocialWorldService().process_world_events(conn, [event])
        reports = int(
            conn.execute(
                "SELECT COUNT(*) FROM npc_knowledge "
                "WHERE knower_actor_id = 'npc_kaspar' AND source_kind = 'npc_report'"
            ).fetchone()[0]
        )
        assert reports == 0
        conn.execute("ROLLBACK")
