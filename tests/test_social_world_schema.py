from __future__ import annotations

import sqlite3

import pytest

from samseberpg.db import DEFAULT_WORLD_ID, GameDatabase


def test_social_world_schema_exists(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    with db.connect() as conn:
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert "npc_knowledge" in tables
        assert "social_processed_events" in tables

        columns = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(npc_knowledge)").fetchall()
        }
        assert {
            "world_id",
            "knower_actor_id",
            "subject_actor_id",
            "fact_key",
            "fact_text",
            "source_kind",
            "source_actor_id",
            "source_world_event_id",
            "source_knowledge_id",
            "confidence",
            "shareable",
            "learned_tick",
            "created_at",
        }.issubset(columns)


def test_npc_knowledge_is_unique_per_knower_and_fact(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    with db.connect() as conn:
        tick = int(
            conn.execute(
                "SELECT tick FROM world_runtime WHERE world_id = ?",
                (DEFAULT_WORLD_ID,),
            ).fetchone()[0]
        )
        params = (
            DEFAULT_WORLD_ID,
            "npc_mira",
            None,
            "schema-test-fact",
            "A schema-level social fact.",
            "direct_event",
            None,
            100,
            1,
            tick,
            "2026-09-04T00:00:00Z",
        )
        statement = (
            "INSERT INTO npc_knowledge "
            "(world_id, knower_actor_id, subject_actor_id, fact_key, fact_text, "
            "source_kind, source_actor_id, confidence, shareable, learned_tick, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        conn.execute(statement, params)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(statement, params)


def test_social_knowledge_survives_database_reopen(tmp_path):
    path = tmp_path / "world.sqlite3"
    db = GameDatabase(path)
    db.initialize()

    with db.connect() as conn:
        conn.execute(
            "INSERT INTO npc_knowledge "
            "(world_id, knower_actor_id, subject_actor_id, fact_key, fact_text, "
            "source_kind, source_actor_id, confidence, shareable, learned_tick, created_at) "
            "VALUES (?, 'npc_mira', NULL, 'reopen-fact', 'Persistent fact.', "
            "'direct_event', NULL, 100, 0, 0, '2026-09-04T00:00:00Z')",
            (DEFAULT_WORLD_ID,),
        )

    reopened = GameDatabase(path)
    reopened.initialize()
    with reopened.connect() as conn:
        row = conn.execute(
            "SELECT fact_text FROM npc_knowledge "
            "WHERE knower_actor_id = 'npc_mira' AND fact_key = 'reopen-fact'"
        ).fetchone()
        assert row is not None
        assert row[0] == "Persistent fact."
