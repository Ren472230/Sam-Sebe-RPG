from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class GameDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS world_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS entities (
                    entity_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    location_id TEXT,
                    item_kind TEXT,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    state_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS player_state (
                    player_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    location_id TEXT NOT NULL
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
                    metadata_json TEXT NOT NULL DEFAULT '{}',
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
                    profile_key TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    PRIMARY KEY (player_id, profile_key)
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
                    unlocked_at INTEGER NOT NULL,
                    mechanic_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (player_id, ability_id)
                );
                """
            )

    def bootstrap_if_empty(self) -> None:
        with self.connect() as connection:
            if connection.execute(
                "SELECT 1 FROM world_meta WHERE key = 'bootstrap_complete'"
            ).fetchone():
                return

            connection.executemany(
                "INSERT OR IGNORE INTO world_meta(key, value) VALUES (?, ?)",
                [("world_time", "0"), ("schema_version", "1")],
            )

            entities: list[tuple[str, str, str, str | None, str | None, str, str]] = [
                ("workshop_yard", "location", "Двор мастерской", None, None, "[]", json.dumps({"connections": ["village_square"]}, ensure_ascii=False)),
                ("village_square", "location", "Деревенская площадь", None, None, "[]", json.dumps({"connections": ["workshop_yard", "river_edge"]}, ensure_ascii=False)),
                ("river_edge", "location", "Берег реки", None, None, "[]", json.dumps({"connections": ["village_square"]}, ensure_ascii=False)),
                ("mira_craftswoman", "npc", "Мира", "workshop_yard", None, "[]", "{}"),
                ("oren_innkeeper", "npc", "Орен", "village_square", None, "[]", "{}"),
                ("kaspar_forager", "npc", "Каспар", "river_edge", None, "[]", "{}"),
                ("raven_1", "animal", "Ворон", "river_edge", None, "[]", json.dumps({"trust": 0, "fear": 0})),
                ("raven_2", "animal", "Ворон", "river_edge", None, "[]", json.dumps({"trust": 0, "fear": 0})),
                ("target_barrel", "target", "Старая бочка", "workshop_yard", None, "[]", "{}"),
                ("stone_flat_1", "item", "Плоский камень", "workshop_yard", "stone_flat", json.dumps(["improvised_projectile"]), "{}"),
                ("stone_round_1", "item", "Круглый камень", "workshop_yard", "stone_round", json.dumps(["improvised_projectile"]), "{}"),
                ("apple_1", "item", "Яблоко", "village_square", "food", json.dumps(["food"]), "{}"),
                ("bread_1", "item", "Хлеб", "village_square", "food", json.dumps(["food"]), "{}"),
                ("rope_1", "item", "Верёвка", "river_edge", "utility", json.dumps(["utility"]), "{}"),
            ]
            connection.executemany(
                """
                INSERT OR IGNORE INTO entities(
                    entity_id, entity_type, name, location_id, item_kind, tags_json, state_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                entities,
            )
            connection.execute(
                "INSERT OR IGNORE INTO player_state(player_id, name, location_id) VALUES (?, ?, ?)",
                ("player_1", "Путник", "workshop_yard"),
            )
            connection.execute(
                "INSERT OR REPLACE INTO world_meta(key, value) VALUES ('bootstrap_complete', '1')"
            )

    def fetch_player(self, player_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM player_state WHERE player_id = ?", (player_id,)
            ).fetchone()

    def fetch_entity(self, entity_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM entities WHERE entity_id = ?", (entity_id,)
            ).fetchone()

    def list_inventory(self, player_id: str) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT e.* FROM inventory i
                    JOIN entities e ON e.entity_id = i.item_id
                    WHERE i.player_id = ?
                    ORDER BY e.entity_id
                    """,
                    (player_id,),
                ).fetchall()
            )

    def list_events(self, actor_id: str | None = None) -> list[sqlite3.Row]:
        with self.connect() as connection:
            if actor_id is None:
                rows = connection.execute(
                    "SELECT * FROM action_events ORDER BY event_id"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM action_events WHERE actor_id = ? ORDER BY event_id",
                    (actor_id,),
                ).fetchall()
        return list(rows)

    def get_world_time(self) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value FROM world_meta WHERE key = 'world_time'"
            ).fetchone()
        return int(row["value"]) if row else 0

    def decode_entity(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["tags"] = json.loads(data.pop("tags_json"))
        data["state"] = json.loads(data.pop("state_json"))
        return data
