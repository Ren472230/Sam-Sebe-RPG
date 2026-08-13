from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


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
        {},
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
        {},
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
