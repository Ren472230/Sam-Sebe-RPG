from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


LATEST_SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    location_id TEXT,
    tags_json TEXT NOT NULL DEFAULT '[]',
    state_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS player_state (
    player_id TEXT PRIMARY KEY,
    location_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS player_resources (
    player_id TEXT PRIMARY KEY,
    coins INTEGER NOT NULL DEFAULT 0,
    lodging_secured INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS inventory (
    player_id TEXT NOT NULL,
    item_id TEXT NOT NULL UNIQUE,
    PRIMARY KEY (player_id, item_id)
);

CREATE TABLE IF NOT EXISTS relations (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    value REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (source_id, target_id, relation_type)
);

CREATE TABLE IF NOT EXISTS action_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_time INTEGER NOT NULL,
    started_at_tick INTEGER NOT NULL DEFAULT 0,
    resolved_at_tick INTEGER NOT NULL DEFAULT 0,
    duration_ticks INTEGER NOT NULL DEFAULT 0,
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

CREATE TABLE IF NOT EXISTS input_attempts (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_time INTEGER NOT NULL,
    raw_text TEXT NOT NULL,
    parser_mode TEXT NOT NULL,
    parser_model TEXT,
    recognized INTEGER NOT NULL,
    canonical_action_json TEXT,
    result_code TEXT,
    parser_error TEXT,
    latency_ms REAL
);

CREATE TABLE IF NOT EXISTS world_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_time INTEGER NOT NULL,
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    target_id TEXT,
    location_id TEXT,
    data_json TEXT NOT NULL DEFAULT '{}',
    summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS behavior_profiles (
    player_id TEXT NOT NULL,
    behavior_key TEXT NOT NULL,
    data_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (player_id, behavior_key)
);

CREATE TABLE IF NOT EXISTS achievements (
    player_id TEXT NOT NULL,
    achievement_id TEXT NOT NULL,
    unlocked_at INTEGER NOT NULL,
    PRIMARY KEY (player_id, achievement_id)
);

CREATE TABLE IF NOT EXISTS abilities (
    player_id TEXT NOT NULL,
    ability_id TEXT NOT NULL,
    mechanic_json TEXT NOT NULL,
    unlocked_at INTEGER NOT NULL,
    PRIMARY KEY (player_id, ability_id)
);
"""


BOOTSTRAP_ENTITIES: tuple[
    tuple[str, str, str, str | None, list[str], dict[str, Any]], ...
] = (
    ("workshop_yard", "location", "Двор мастерской", None, ["location"], {}),
    ("village_square", "location", "Деревенская площадь", None, ["location"], {}),
    ("river_edge", "location", "Берег реки", None, ["location"], {}),
    (
        "mira_craftswoman",
        "npc",
        "Мира, ремесленница",
        "workshop_yard",
        ["npc"],
        {"wood_stock": 2, "work_cycles": 0, "requested_wood": False},
    ),
    (
        "oren_innkeeper",
        "npc",
        "Орен, трактирщик",
        "village_square",
        ["npc"],
        {},
    ),
    (
        "kaspar_forager",
        "npc",
        "Каспар, собиратель",
        "river_edge",
        ["npc"],
        {"carrying_wood": 0},
    ),
    (
        "raven_1",
        "animal",
        "Ворон",
        "village_square",
        ["animal", "raven"],
        {"trust": 0, "fear": 0},
    ),
    (
        "raven_2",
        "animal",
        "Молодой ворон",
        "river_edge",
        ["animal", "raven"],
        {"trust": 0, "fear": 0},
    ),
    (
        "target_barrel",
        "object",
        "Старая бочка",
        "workshop_yard",
        ["throw_target"],
        {},
    ),
    (
        "target_sign",
        "object",
        "Вывеска трактира",
        "village_square",
        ["throw_target"],
        {},
    ),
    (
        "target_post",
        "object",
        "Корявая стойка",
        "river_edge",
        ["throw_target"],
        {},
    ),
    (
        "stone_flat_1",
        "item",
        "Плоский камень",
        "workshop_yard",
        ["improvised_projectile", "flat_stone"],
        {},
    ),
    (
        "stone_round_1",
        "item",
        "Круглый камень",
        "workshop_yard",
        ["improvised_projectile", "round_stone"],
        {},
    ),
    (
        "pinecone_1",
        "item",
        "Сосновая шишка",
        "river_edge",
        ["improvised_projectile", "pinecone"],
        {},
    ),
    (
        "driftwood_1",
        "item",
        "Сухая коряга",
        "river_edge",
        ["useful_wood"],
        {},
    ),
    ("bread_1", "item", "Кусок хлеба", "village_square", ["food"], {}),
)


class GameDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO world_meta(key, value) VALUES ('world_time', '0')"
            )
            version_row = conn.execute(
                "SELECT value FROM world_meta WHERE key = 'schema_version'"
            ).fetchone()
            if version_row is None:
                timing_columns = {
                    "started_at_tick",
                    "resolved_at_tick",
                    "duration_ticks",
                }
                inferred_version = (
                    LATEST_SCHEMA_VERSION
                    if timing_columns <= self._table_columns(conn, "action_events")
                    else 1
                )
                conn.execute(
                    "INSERT INTO world_meta(key, value) VALUES ('schema_version', ?)",
                    (str(inferred_version),),
                )
                version = inferred_version
            else:
                version = int(version_row["value"])

            if version < 2:
                self._migrate_1_to_2(conn)
                version = 2
            if version != LATEST_SCHEMA_VERSION:
                raise RuntimeError(f"Unsupported schema version: {version}")

    def _migrate_1_to_2(self, conn: sqlite3.Connection) -> None:
        columns = self._table_columns(conn, "action_events")
        if "started_at_tick" not in columns:
            conn.execute(
                "ALTER TABLE action_events ADD COLUMN started_at_tick INTEGER NOT NULL DEFAULT 0"
            )
        if "resolved_at_tick" not in columns:
            conn.execute(
                "ALTER TABLE action_events ADD COLUMN resolved_at_tick INTEGER NOT NULL DEFAULT 0"
            )
        if "duration_ticks" not in columns:
            conn.execute(
                "ALTER TABLE action_events ADD COLUMN duration_ticks INTEGER NOT NULL DEFAULT 0"
            )
        conn.execute(
            """
            UPDATE action_events
            SET started_at_tick = world_time,
                resolved_at_tick = world_time,
                duration_ticks = 0
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS input_attempts (
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                world_time INTEGER NOT NULL,
                raw_text TEXT NOT NULL,
                parser_mode TEXT NOT NULL,
                parser_model TEXT,
                recognized INTEGER NOT NULL,
                canonical_action_json TEXT,
                result_code TEXT,
                parser_error TEXT,
                latency_ms REAL
            )
            """
        )
        conn.execute(
            "UPDATE world_meta SET value = '2' WHERE key = 'schema_version'"
        )

    def _table_columns(self, conn: sqlite3.Connection, table_name: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row["name"]) for row in rows}

    def table_columns(self, table_name: str) -> set[str]:
        with self.connect() as conn:
            return self._table_columns(conn, table_name)

    def get_schema_version(self) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT value FROM world_meta WHERE key = 'schema_version'"
            ).fetchone()
        return int(row["value"]) if row else 0

    def record_input_attempt(
        self,
        *,
        world_time: int,
        raw_text: str,
        parser_mode: str,
        parser_model: str | None,
        recognized: bool,
        canonical_action: dict[str, Any] | None,
        parser_error: str | None,
        latency_ms: float | None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO input_attempts(
                    world_time, raw_text, parser_mode, parser_model, recognized,
                    canonical_action_json, parser_error, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    world_time,
                    raw_text,
                    parser_mode,
                    parser_model,
                    int(recognized),
                    json.dumps(canonical_action, ensure_ascii=False)
                    if canonical_action is not None
                    else None,
                    parser_error,
                    latency_ms,
                ),
            )
            return int(cursor.lastrowid)

    def complete_input_attempt(self, attempt_id: int, result_code: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE input_attempts SET result_code = ? WHERE attempt_id = ?",
                (result_code, attempt_id),
            )

    def list_input_attempts(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM input_attempts ORDER BY attempt_id"
            ).fetchall()
        attempts: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["recognized"] = bool(data["recognized"])
            raw_action = data.pop("canonical_action_json")
            data["canonical_action"] = json.loads(raw_action) if raw_action else None
            attempts.append(data)
        return attempts

    def bootstrap_if_empty(self) -> None:
        """Idempotently add bootstrap data, including upgrades for older pilot DBs."""
        with self.connect() as conn:
            for entity_id, entity_type, name, location_id, tags, state in BOOTSTRAP_ENTITIES:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO entities(
                        entity_id, entity_type, name, location_id, tags_json, state_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entity_id,
                        entity_type,
                        name,
                        location_id,
                        json.dumps(tags),
                        json.dumps(state),
                    ),
                )
            living_world_defaults = {
                "mira_craftswoman": {
                    "wood_stock": 2,
                    "work_cycles": 0,
                    "requested_wood": False,
                },
                "kaspar_forager": {"carrying_wood": 0},
            }
            for entity_id, defaults in living_world_defaults.items():
                row = conn.execute(
                    "SELECT state_json FROM entities WHERE entity_id = ?",
                    (entity_id,),
                ).fetchone()
                if row is None:
                    continue
                state = json.loads(row["state_json"])
                changed = False
                for key, value in defaults.items():
                    if key not in state:
                        state[key] = value
                        changed = True
                if changed:
                    conn.execute(
                        "UPDATE entities SET state_json = ? WHERE entity_id = ?",
                        (json.dumps(state, ensure_ascii=False), entity_id),
                    )

            conn.execute(
                """
                INSERT OR IGNORE INTO player_state(player_id, location_id)
                VALUES (?, ?)
                """,
                ("player_1", "workshop_yard"),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO player_resources(
                    player_id, coins, lodging_secured
                ) VALUES (?, 0, 0)
                """,
                ("player_1",),
            )

    def list_tables(self) -> set[str]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """
            ).fetchall()
        return {row["name"] for row in rows}

    def fetch_player_resources(self, player_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT coins, lodging_secured
                FROM player_resources
                WHERE player_id = ?
                """,
                (player_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "coins": int(row["coins"]),
            "lodging_secured": bool(row["lodging_secured"]),
        }

    def fetch_player(self, player_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT player_id, location_id FROM player_state WHERE player_id = ?",
                (player_id,),
            ).fetchone()
        return dict(row) if row else None

    def fetch_entity(self, entity_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT entity_id, entity_type, name, location_id, tags_json, state_json
                FROM entities
                WHERE entity_id = ?
                """,
                (entity_id,),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["tags"] = json.loads(data.pop("tags_json"))
        data["state"] = json.loads(data.pop("state_json"))
        return data

    def list_inventory(self, player_id: str) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT item_id
                FROM inventory
                WHERE player_id = ?
                ORDER BY item_id
                """,
                (player_id,),
            ).fetchall()
        return [row["item_id"] for row in rows]

    def list_events(self, player_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM action_events"
        params: tuple[Any, ...] = ()
        if player_id is not None:
            query += " WHERE actor_id = ?"
            params = (player_id,)
        query += " ORDER BY event_id"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()

        events: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["success"] = bool(data["success"])
            data["behavior_tags"] = json.loads(data.pop("behavior_tags_json"))
            data["evidence"] = json.loads(data.pop("evidence_json"))
            events.append(data)
        return events

    def list_world_events(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM world_events ORDER BY event_id"
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["data"] = json.loads(data.pop("data_json"))
            events.append(data)
        return events

    def get_world_time(self) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT value FROM world_meta WHERE key = 'world_time'"
            ).fetchone()
        return int(row["value"]) if row else 0

    def has_achievement(self, player_id: str, achievement_id: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM achievements
                WHERE player_id = ? AND achievement_id = ?
                """,
                (player_id, achievement_id),
            ).fetchone()
        return row is not None

    def has_ability(self, player_id: str, ability_id: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM abilities
                WHERE player_id = ? AND ability_id = ?
                """,
                (player_id, ability_id),
            ).fetchone()
        return row is not None

    def fetch_behavior_profile(
        self, player_id: str, behavior_key: str
    ) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT data_json
                FROM behavior_profiles
                WHERE player_id = ? AND behavior_key = ?
                """,
                (player_id, behavior_key),
            ).fetchone()
        return json.loads(row["data_json"]) if row else None

    def fetch_ability(self, player_id: str, ability_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT ability_id, mechanic_json, unlocked_at
                FROM abilities
                WHERE player_id = ? AND ability_id = ?
                """,
                (player_id, ability_id),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["mechanic"] = json.loads(data.pop("mechanic_json"))
        return data
