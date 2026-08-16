from __future__ import annotations

import json
import sqlite3
from pathlib import Path


DEFAULT_WORLD_ID = "village_1"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS worlds (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_simulated_at TEXT
);

CREATE TABLE IF NOT EXISTS locations (
    id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    sort_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS location_edges (
    from_location_id TEXT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    to_location_id TEXT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    PRIMARY KEY (from_location_id, to_location_id),
    CHECK (from_location_id <> to_location_id)
);

CREATE TABLE IF NOT EXISTS actors (
    id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('player', 'npc')),
    name TEXT NOT NULL,
    location_id TEXT REFERENCES locations(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS players (
    actor_id TEXT PRIMARY KEY REFERENCES actors(id) ON DELETE CASCADE,
    discord_user_id TEXT NOT NULL UNIQUE,
    joined_at TEXT NOT NULL,
    coins INTEGER NOT NULL DEFAULT 10 CHECK (coins >= 0)
);

CREATE TABLE IF NOT EXISTS npcs (
    actor_id TEXT PRIMARY KEY REFERENCES actors(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    current_activity TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS npc_schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    npc_actor_id TEXT NOT NULL REFERENCES npcs(actor_id) ON DELETE CASCADE,
    start_minute_local INTEGER NOT NULL CHECK (start_minute_local BETWEEN 0 AND 1439),
    end_minute_local INTEGER NOT NULL CHECK (end_minute_local BETWEEN 0 AND 1439),
    location_id TEXT NOT NULL REFERENCES locations(id),
    activity TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    UNIQUE (npc_actor_id, start_minute_local, end_minute_local, priority)
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    location_id TEXT REFERENCES locations(id),
    owner_actor_id TEXT REFERENCES actors(id),
    portable INTEGER NOT NULL CHECK (portable IN (0, 1)),
    state_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    CHECK (NOT (location_id IS NOT NULL AND owner_actor_id IS NOT NULL))
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
    CHECK (source_actor_id <> target_actor_id)
);

CREATE TABLE IF NOT EXISTS action_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id TEXT NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    external_id TEXT UNIQUE,
    occurred_at TEXT NOT NULL,
    actor_id TEXT REFERENCES actors(id),
    action_type TEXT NOT NULL,
    target_id TEXT,
    location_id TEXT REFERENCES locations(id),
    success INTEGER NOT NULL CHECK (success IN (0, 1)),
    result_code TEXT NOT NULL,
    summary TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS processed_interactions (
    external_id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    actor_id TEXT REFERENCES actors(id),
    action_event_id INTEGER NOT NULL REFERENCES action_events(id) ON DELETE CASCADE,
    result_json TEXT NOT NULL,
    processed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_actors_location ON actors(location_id);
CREATE INDEX IF NOT EXISTS idx_entities_location ON entities(location_id);
CREATE INDEX IF NOT EXISTS idx_entities_owner ON entities(owner_actor_id);
CREATE INDEX IF NOT EXISTS idx_events_world_time ON action_events(world_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_schedule_npc ON npc_schedule(npc_actor_id, priority DESC);
"""


_LOCATIONS = (
    (
        "workshop_yard",
        "Workshop Yard",
        "A compact yard of benches, timber scraps, tools, and a weathered stone wall.",
        10,
    ),
    (
        "village_square",
        "Village Square",
        "The social center of the village, ringed by a well, an inn, and market tables.",
        20,
    ),
    (
        "river_edge",
        "River Edge",
        "A reed-lined bank where the village path meets a shallow bend in the river.",
        30,
    ),
)

_EDGES = (
    ("workshop_yard", "village_square"),
    ("village_square", "workshop_yard"),
    ("village_square", "river_edge"),
    ("river_edge", "village_square"),
)

_NPCS = (
    ("npc_mira", "Mira", "workshop_yard", "craftswoman", "working at the bench"),
    ("npc_oren", "Oren", "village_square", "innkeeper", "preparing the inn"),
    ("npc_kaspar", "Kaspar", "river_edge", "forager", "checking the riverbank"),
)

_SCHEDULE = (
    ("npc_mira", 360, 1080, "workshop_yard", "working at the bench", 10),
    ("npc_mira", 1080, 1320, "village_square", "running evening errands", 10),
    ("npc_mira", 1320, 360, "workshop_yard", "resting near the workshop", 10),
    ("npc_oren", 300, 1380, "village_square", "running the inn", 10),
    ("npc_oren", 1380, 300, "village_square", "sleeping upstairs", 10),
    ("npc_kaspar", 360, 960, "river_edge", "foraging along the river", 10),
    ("npc_kaspar", 960, 1260, "village_square", "trading gathered goods", 10),
    ("npc_kaspar", 1260, 360, "river_edge", "camping by the river", 10),
)

_ENTITIES = (
    (
        "stone_flat_1",
        "Flat Stone",
        "stone",
        "workshop_yard",
        1,
        {"tags": ["improvised_projectile"], "projectile_type": "flat_stone"},
    ),
    (
        "wood_block_1",
        "Wood Block",
        "material",
        "workshop_yard",
        1,
        {"tags": ["improvised_projectile"], "projectile_type": "wood_block"},
    ),
    ("hammer_old_1", "Old Hammer", "tool", "workshop_yard", 1, {"condition": "worn"}),
    ("anvil_1", "Small Anvil", "fixture", "workshop_yard", 0, {}),
    ("bread_loaf_1", "Loaf of Bread", "food", "village_square", 1, {"fresh": True}),
    ("mug_clay_1", "Clay Mug", "container", "village_square", 1, {}),
    ("market_crate_1", "Market Crate", "fixture", "village_square", 0, {}),
    ("rope_coil_1", "Coil of Rope", "tool", "village_square", 1, {}),
    ("reed_bundle_1", "Bundle of Reeds", "material", "river_edge", 1, {}),
    (
        "smooth_pebble_1",
        "Smooth Pebble",
        "stone",
        "river_edge",
        1,
        {"tags": ["improvised_projectile"], "projectile_type": "smooth_pebble"},
    ),
    ("fishing_net_1", "Fishing Net", "tool", "river_edge", 1, {"condition": "patched"}),
    ("river_marker_1", "River Marker", "fixture", "river_edge", 0, {}),
)


class GameDatabase:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.path),
            timeout=5.0,
            isolation_level=None,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        if str(self.path) != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = self.connect()
        try:
            conn.executescript(_SCHEMA)
            conn.execute("BEGIN IMMEDIATE")
            try:
                self._bootstrap(conn)
            except Exception:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")
        finally:
            conn.close()

    def _bootstrap(self, conn: sqlite3.Connection) -> None:
        created_at = _sqlite_utc_now(conn)

        conn.execute(
            "INSERT OR IGNORE INTO worlds "
            "(id, name, timezone, created_at, last_simulated_at) VALUES (?, ?, ?, ?, NULL)",
            (DEFAULT_WORLD_ID, "MVP Village", "UTC", created_at),
        )

        conn.executemany(
            "INSERT OR IGNORE INTO locations "
            "(id, world_id, name, description, sort_order) VALUES (?, ?, ?, ?, ?)",
            [
                (location_id, DEFAULT_WORLD_ID, name, description, sort_order)
                for location_id, name, description, sort_order in _LOCATIONS
            ],
        )

        conn.executemany(
            "INSERT OR IGNORE INTO location_edges (from_location_id, to_location_id) VALUES (?, ?)",
            _EDGES,
        )

        for actor_id, name, location_id, role, activity in _NPCS:
            conn.execute(
                "INSERT OR IGNORE INTO actors "
                "(id, world_id, actor_type, name, location_id, created_at) "
                "VALUES (?, ?, 'npc', ?, ?, ?)",
                (actor_id, DEFAULT_WORLD_ID, name, location_id, created_at),
            )
            conn.execute(
                "INSERT OR IGNORE INTO npcs (actor_id, role, current_activity) VALUES (?, ?, ?)",
                (actor_id, role, activity),
            )

        conn.executemany(
            "INSERT OR IGNORE INTO npc_schedule "
            "(npc_actor_id, start_minute_local, end_minute_local, location_id, activity, priority) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            _SCHEDULE,
        )

        conn.executemany(
            "INSERT OR IGNORE INTO entities "
            "(id, world_id, name, entity_type, location_id, owner_actor_id, portable, state_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?)",
            [
                (
                    entity_id,
                    DEFAULT_WORLD_ID,
                    name,
                    entity_type,
                    location_id,
                    portable,
                    json.dumps(state, separators=(",", ":"), sort_keys=True),
                    created_at,
                )
                for entity_id, name, entity_type, location_id, portable, state in _ENTITIES
            ],
        )


def _sqlite_utc_now(conn: sqlite3.Connection) -> str:
    return str(
        conn.execute(
            "SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
        ).fetchone()[0]
    )
