from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

WORLD_ID = "village_1"
START_LOCATION_ID = "workshop_yard"
SCHEMA_VERSION = 3


class UnsupportedSchemaVersionError(RuntimeError):
    pass


def to_utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


SCHEMA = """
CREATE TABLE IF NOT EXISTS worlds (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_simulated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS locations (
    id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    sort_order INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS location_edges (
    world_id TEXT NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    from_location_id TEXT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    to_location_id TEXT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    PRIMARY KEY (world_id, from_location_id, to_location_id)
);
CREATE TABLE IF NOT EXISTS actors (
    id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    actor_type TEXT NOT NULL CHECK(actor_type IN ('player', 'npc')),
    name TEXT NOT NULL,
    location_id TEXT NOT NULL REFERENCES locations(id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS players (
    actor_id TEXT PRIMARY KEY REFERENCES actors(id) ON DELETE CASCADE,
    discord_user_id TEXT NOT NULL UNIQUE,
    joined_at TEXT NOT NULL,
    coins INTEGER NOT NULL DEFAULT 10 CHECK(coins >= 0)
);
CREATE TABLE IF NOT EXISTS npcs (
    actor_id TEXT PRIMARY KEY REFERENCES actors(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    current_activity TEXT NOT NULL,
    coins INTEGER NOT NULL DEFAULT 0 CHECK(coins >= 0)
);
CREATE TABLE IF NOT EXISTS npc_schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    npc_actor_id TEXT NOT NULL REFERENCES npcs(actor_id) ON DELETE CASCADE,
    start_minute_local INTEGER NOT NULL CHECK(start_minute_local BETWEEN 0 AND 1439),
    end_minute_local INTEGER NOT NULL CHECK(end_minute_local BETWEEN 0 AND 1439),
    location_id TEXT NOT NULL REFERENCES locations(id),
    activity TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    location_id TEXT REFERENCES locations(id),
    owner_actor_id TEXT REFERENCES actors(id),
    portable INTEGER NOT NULL CHECK(portable IN (0, 1)),
    state_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    CHECK ((location_id IS NULL) != (owner_actor_id IS NULL))
);
CREATE TABLE IF NOT EXISTS relations (
    source_actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
    target_actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
    familiarity INTEGER NOT NULL DEFAULT 0,
    trust INTEGER NOT NULL DEFAULT 0,
    affinity INTEGER NOT NULL DEFAULT 0,
    fear INTEGER NOT NULL DEFAULT 0,
    conflict INTEGER NOT NULL DEFAULT 0,
    romance INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (source_actor_id, target_actor_id),
    CHECK (source_actor_id != target_actor_id)
);
CREATE TABLE IF NOT EXISTS action_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id TEXT NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    external_id TEXT,
    occurred_at TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    target_id TEXT,
    location_id TEXT,
    success INTEGER NOT NULL CHECK(success IN (0, 1)),
    result_code TEXT NOT NULL,
    summary TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_action_events_actor ON action_events(actor_id, id);
CREATE INDEX IF NOT EXISTS idx_entities_location ON entities(location_id);
CREATE INDEX IF NOT EXISTS idx_entities_owner ON entities(owner_actor_id);
CREATE TABLE IF NOT EXISTS processed_interactions (
    external_id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    actor_id TEXT NOT NULL,
    action_event_id INTEGER NOT NULL REFERENCES action_events(id) ON DELETE CASCADE,
    result_json TEXT NOT NULL,
    processed_at TEXT NOT NULL
);
"""


class GameDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=5.0, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                current_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
                if current_version > SCHEMA_VERSION:
                    raise UnsupportedSchemaVersionError(
                        f"database schema version {current_version} is newer than supported {SCHEMA_VERSION}"
                    )
                for statement in SCHEMA.split(";"):
                    statement = statement.strip()
                    if statement:
                        conn.execute(statement)
                for target_version in range(current_version + 1, SCHEMA_VERSION + 1):
                    self._apply_migration(conn, target_version)
                    conn.execute(f"PRAGMA user_version = {target_version}")
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _apply_migration(self, conn: sqlite3.Connection, target_version: int) -> None:
        if target_version == 1:
            self._migrate_add_npc_currency(conn)
            return
        if target_version == 2:
            self._migrate_seed_affordances(conn)
            return
        if target_version == 3:
            self._migrate_add_progression_tables(conn)
            return
        raise UnsupportedSchemaVersionError(f"no migration for schema version {target_version}")

    @staticmethod
    def _migrate_add_npc_currency(conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(npcs)")}
        if "coins" in columns:
            return
        conn.execute("ALTER TABLE npcs ADD COLUMN coins INTEGER NOT NULL DEFAULT 0 CHECK(coins >= 0)")
        conn.execute("UPDATE npcs SET coins = 20 WHERE actor_id = 'npc_oren'")

    @staticmethod
    def _migrate_add_progression_tables(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_achievements (
                player_actor_id TEXT NOT NULL REFERENCES players(actor_id) ON DELETE CASCADE,
                achievement_code TEXT NOT NULL,
                unlocked_at TEXT NOT NULL,
                trigger_event_id INTEGER NOT NULL REFERENCES action_events(id) ON DELETE RESTRICT,
                evidence_json TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY (player_actor_id, achievement_code)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_abilities (
                player_actor_id TEXT NOT NULL REFERENCES players(actor_id) ON DELETE CASCADE,
                ability_code TEXT NOT NULL,
                unlocked_at TEXT NOT NULL,
                source_achievement_code TEXT NOT NULL,
                PRIMARY KEY (player_actor_id, ability_code)
            )
            """
        )

    @staticmethod
    def _migrate_seed_affordances(conn: sqlite3.Connection) -> None:
        defaults = {
            "stone_flat_1": {"throwable": True, "impact_damage": 20},
            "stone_round_1": {"throwable": True, "impact_damage": 20},
            "bottle_1": {"price": 3, "for_sale_by": "npc_oren", "fillable": True, "filled_with": None},
            "village_well": {"water_source": True},
        }
        for entity_id, missing_defaults in defaults.items():
            row = conn.execute("SELECT state_json FROM entities WHERE id = ?", (entity_id,)).fetchone()
            if row is None:
                continue
            state = json.loads(row["state_json"])
            before = dict(state)
            for key, value in missing_defaults.items():
                state.setdefault(key, value)
            if state != before:
                conn.execute(
                    "UPDATE entities SET state_json = ? WHERE id = ?",
                    (json.dumps(state, ensure_ascii=False, sort_keys=True), entity_id),
                )

    def bootstrap_if_empty(self, now: datetime) -> None:
        timestamp = to_utc_text(now)
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                if conn.execute("SELECT 1 FROM worlds WHERE id = ?", (WORLD_ID,)).fetchone():
                    conn.commit()
                    return
                conn.execute(
                    "INSERT INTO worlds(id, name, timezone, created_at, last_simulated_at) VALUES (?, ?, ?, ?, ?)",
                    (WORLD_ID, "Пограничная деревня", "UTC", timestamp, timestamp),
                )
                locations = [
                    ("workshop_yard", WORLD_ID, "Двор мастерской", "Двор Миры: верстак, навес и следы ремесленной работы.", 1),
                    ("village_square", WORLD_ID, "Деревенская площадь", "Небольшая площадь перед таверной и колодцем.", 2),
                    ("river_edge", WORLD_ID, "Берег реки", "Тихий берег у лесной кромки, где собирают травы и камни.", 3),
                ]
                conn.executemany("INSERT INTO locations(id, world_id, name, description, sort_order) VALUES (?, ?, ?, ?, ?)", locations)
                edges = [
                    (WORLD_ID, "workshop_yard", "village_square"),
                    (WORLD_ID, "village_square", "workshop_yard"),
                    (WORLD_ID, "village_square", "river_edge"),
                    (WORLD_ID, "river_edge", "village_square"),
                ]
                conn.executemany("INSERT INTO location_edges(world_id, from_location_id, to_location_id) VALUES (?, ?, ?)", edges)
                npc_rows = [
                    ("npc_mira", WORLD_ID, "npc", "Мира", "workshop_yard", timestamp, "ремесленница", "работает за верстаком"),
                    ("npc_oren", WORLD_ID, "npc", "Орен", "village_square", timestamp, "трактирщик", "готовит таверну к посетителям"),
                    ("npc_kaspar", WORLD_ID, "npc", "Каспар", "river_edge", timestamp, "собиратель", "ищет полезные травы"),
                ]
                conn.executemany(
                    "INSERT INTO actors(id, world_id, actor_type, name, location_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    [row[:6] for row in npc_rows],
                )
                conn.executemany(
                    "INSERT INTO npcs(actor_id, role, current_activity, coins) VALUES (?, ?, ?, ?)",
                    [(row[0], row[6], row[7], 20 if row[0] == "npc_oren" else 0) for row in npc_rows],
                )
                schedules = [
                    ("npc_mira", 360, 1080, "workshop_yard", "работает за верстаком", 10),
                    ("npc_mira", 1080, 360, "village_square", "ужинает и разговаривает в таверне", 10),
                    ("npc_oren", 360, 60, "village_square", "держит таверну открытой", 10),
                    ("npc_oren", 60, 360, "village_square", "спит в комнате над таверной", 10),
                    ("npc_kaspar", 360, 1080, "river_edge", "ищет травы у реки", 10),
                    ("npc_kaspar", 1080, 360, "village_square", "возвращается с добычей в деревню", 10),
                ]
                conn.executemany(
                    "INSERT INTO npc_schedule(npc_actor_id, start_minute_local, end_minute_local, location_id, activity, priority) VALUES (?, ?, ?, ?, ?, ?)",
                    schedules,
                )
                entities = [
                    ("stone_flat_1", "Плоский камень", "stone", "workshop_yard", 1, {"throwable": True, "impact_damage": 20}),
                    ("stone_round_1", "Круглый камень", "stone", "workshop_yard", 1, {"throwable": True, "impact_damage": 20}),
                    ("bread_1", "Каравай хлеба", "food", "village_square", 1, {"edible": True}),
                    ("apple_1", "Красное яблоко", "food", "village_square", 1, {"edible": True}),
                    ("bottle_1", "Пустая бутылка", "container", "village_square", 1, {"price": 3, "for_sale_by": "npc_oren", "fillable": True, "filled_with": None}),
                    ("bucket_1", "Деревянное ведро", "tool", "workshop_yard", 1, {}),
                    ("rope_1", "Короткая верёвка", "tool", "workshop_yard", 1, {}),
                    ("herb_bundle_1", "Пучок речных трав", "resource", "river_edge", 1, {}),
                    ("driftwood_1", "Сухая коряга", "resource", "river_edge", 1, {}),
                    ("tavern_sign", "Вывеска таверны", "fixture", "village_square", 0, {"condition": 100}),
                    ("village_well", "Колодец", "fixture", "village_square", 0, {"water_source": True}),
                    ("workbench", "Верстак Миры", "fixture", "workshop_yard", 0, {}),
                ]
                conn.executemany(
                    "INSERT INTO entities(id, world_id, name, entity_type, location_id, owner_actor_id, portable, state_json, created_at) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?)",
                    [(entity_id, WORLD_ID, name, entity_type, location_id, portable, json.dumps(state, ensure_ascii=False), timestamp) for entity_id, name, entity_type, location_id, portable, state in entities],
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
