from __future__ import annotations

import sqlite3
from pathlib import Path

from samseberpg.db import GameDatabase


def _create_pre_audit_database(path: Path) -> GameDatabase:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE world_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE entities (
            entity_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            name TEXT NOT NULL,
            location_id TEXT,
            tags_json TEXT NOT NULL DEFAULT '[]',
            state_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE action_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            world_time INTEGER NOT NULL,
            actor_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            target_id TEXT,
            item_id TEXT,
            location_id TEXT,
            success INTEGER NOT NULL,
            result_code TEXT NOT NULL,
            behavior_tags_json TEXT NOT NULL DEFAULT '[]',
            evidence_json TEXT NOT NULL DEFAULT '{}',
            summary TEXT NOT NULL
        );
        """
    )
    conn.execute("INSERT INTO world_meta(key, value) VALUES ('world_time', '7')")
    conn.execute(
        """
        INSERT INTO entities(entity_id, entity_type, name, location_id, tags_json, state_json)
        VALUES ('mira_craftswoman', 'npc', 'Мира', 'workshop_yard', '[\"npc\"]',
                '{\"sentinel\":\"keep\"}')
        """
    )
    conn.execute(
        """
        INSERT INTO action_events(
            world_time, actor_id, action_type, location_id, success, result_code,
            behavior_tags_json, evidence_json, summary
        ) VALUES (7, 'player_1', 'LOOK', 'workshop_yard', 1, 'OK', '[]', '{}', 'legacy')
        """
    )
    conn.commit()
    conn.close()
    return GameDatabase(path)


def test_fresh_database_is_schema_v2(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "fresh.db")
    db.initialize()

    assert db.get_schema_version() == 2
    assert "input_attempts" in db.list_tables()
    assert {"started_at_tick", "resolved_at_tick", "duration_ticks"} <= db.table_columns(
        "action_events"
    )


def test_pre_audit_database_migrates_without_losing_state(tmp_path: Path) -> None:
    db = _create_pre_audit_database(tmp_path / "legacy.db")

    db.initialize()

    assert db.get_schema_version() == 2
    mira = db.fetch_entity("mira_craftswoman")
    assert mira is not None
    assert mira["state"]["sentinel"] == "keep"
    event = db.list_events("player_1")[0]
    assert event["started_at_tick"] == 7
    assert event["resolved_at_tick"] == 7
    assert event["duration_ticks"] == 0


def test_input_attempt_round_trip_and_completion(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "telemetry.db")
    db.initialize()

    attempt_id = db.record_input_attempt(
        world_time=4,
        raw_text="проверю бочку",
        parser_mode="ollama",
        parser_model="qwen-local",
        recognized=True,
        canonical_action={"action_type": "LOOK", "actor_id": "player_1"},
        parser_error=None,
        latency_ms=12.5,
    )
    db.complete_input_attempt(attempt_id, "OK")

    attempt = db.list_input_attempts()[-1]
    assert attempt["attempt_id"] == attempt_id
    assert attempt["raw_text"] == "проверю бочку"
    assert attempt["parser_mode"] == "ollama"
    assert attempt["parser_model"] == "qwen-local"
    assert attempt["recognized"] is True
    assert attempt["canonical_action"] == {
        "action_type": "LOOK",
        "actor_id": "player_1",
    }
    assert attempt["result_code"] == "OK"
    assert attempt["parser_error"] is None
    assert attempt["latency_ms"] == 12.5
