from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase, SCHEMA_VERSION
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


LEGACY_CORE = """
CREATE TABLE worlds (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, timezone TEXT NOT NULL,
    created_at TEXT NOT NULL, last_simulated_at TEXT NOT NULL
);
CREATE TABLE locations (
    id TEXT PRIMARY KEY, world_id TEXT NOT NULL REFERENCES worlds(id),
    name TEXT NOT NULL, description TEXT NOT NULL, sort_order INTEGER NOT NULL
);
CREATE TABLE actors (
    id TEXT PRIMARY KEY, world_id TEXT NOT NULL REFERENCES worlds(id),
    actor_type TEXT NOT NULL, name TEXT NOT NULL,
    location_id TEXT NOT NULL REFERENCES locations(id), created_at TEXT NOT NULL
);
CREATE TABLE players (
    actor_id TEXT PRIMARY KEY REFERENCES actors(id), discord_user_id TEXT NOT NULL UNIQUE,
    joined_at TEXT NOT NULL, coins INTEGER NOT NULL DEFAULT 10 CHECK(coins >= 0)
);
CREATE TABLE npcs (
    actor_id TEXT PRIMARY KEY REFERENCES actors(id),
    role TEXT NOT NULL, current_activity TEXT NOT NULL
);
CREATE TABLE entities (
    id TEXT PRIMARY KEY, world_id TEXT NOT NULL REFERENCES worlds(id), name TEXT NOT NULL,
    entity_type TEXT NOT NULL, location_id TEXT REFERENCES locations(id),
    owner_actor_id TEXT REFERENCES actors(id), portable INTEGER NOT NULL,
    state_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
    CHECK ((location_id IS NULL) != (owner_actor_id IS NULL))
);
CREATE TABLE action_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, world_id TEXT NOT NULL REFERENCES worlds(id),
    external_id TEXT, occurred_at TEXT NOT NULL, actor_id TEXT NOT NULL,
    action_type TEXT NOT NULL, target_id TEXT, location_id TEXT,
    success INTEGER NOT NULL, result_code TEXT NOT NULL,
    summary TEXT NOT NULL, evidence_json TEXT NOT NULL DEFAULT '{}'
);
"""


def build_legacy_db(path: Path) -> None:
    at = "2026-08-14T08:00:00+00:00"
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(LEGACY_CORE)
        conn.execute(
            "INSERT INTO worlds VALUES ('village_1', 'Legacy Village', 'UTC', ?, ?)",
            (at, at),
        )
        conn.execute(
            "INSERT INTO locations VALUES ('village_square', 'village_1', 'Legacy Square', 'Persistent legacy square', 1)"
        )
        conn.execute(
            "INSERT INTO actors VALUES ('npc_oren', 'village_1', 'npc', 'Oren', 'village_square', ?)",
            (at,),
        )
        conn.execute(
            "INSERT INTO npcs(actor_id, role, current_activity) VALUES ('npc_oren', 'innkeeper', 'working')"
        )
        conn.execute(
            "INSERT INTO actors VALUES ('player_legacy', 'village_1', 'player', 'Legacy Player', 'village_square', ?)",
            (at,),
        )
        conn.execute(
            "INSERT INTO players VALUES ('player_legacy', 'legacy-discord', ?, 9)",
            (at,),
        )
        conn.execute(
            """
            INSERT INTO entities VALUES (
                'bottle_1', 'village_1', 'Legacy bottle', 'container',
                'village_square', NULL, 1, ?, ?
            )
            """,
            (json.dumps({"filled_with": None}), at),
        )
        conn.execute(
            """
            INSERT INTO entities VALUES (
                'tavern_sign', 'village_1', 'Legacy sign', 'fixture',
                'village_square', NULL, 0, ?, ?
            )
            """,
            (json.dumps({"condition": 63}), at),
        )
        conn.execute(
            """
            INSERT INTO action_events(
                world_id, occurred_at, actor_id, action_type, success,
                result_code, summary, evidence_json
            ) VALUES ('village_1', ?, 'player_legacy', 'LOOK', 1, 'OK', 'legacy event', '{}')
            """,
            (at,),
        )
        conn.execute("PRAGMA user_version = 0")
        conn.commit()


def main() -> None:
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    with TemporaryDirectory(prefix="sam-sebe-migration-") as temp_dir:
        path = Path(temp_dir) / "legacy.db"
        build_legacy_db(path)
        print("[legacy] DB v0: existing player has 9 coins; sign condition is 63%")

        db = GameDatabase(path)
        db.initialize()
        with db.connect() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            oren = conn.execute(
                "SELECT coins FROM npcs WHERE actor_id = 'npc_oren'"
            ).fetchone()[0]
            sign = json.loads(
                conn.execute(
                    "SELECT state_json FROM entities WHERE id = 'tavern_sign'"
                ).fetchone()[0]
            )
            event_count = conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0]
        assert version == SCHEMA_VERSION
        assert oren == 20
        assert sign["condition"] == 63
        assert event_count == 1
        print(f"[migration] v0 -> v{SCHEMA_VERSION}; Oren currency added; old event/sign preserved")

        game = GameService(db, FakeClock(now))
        view = game.observe("player_legacy")
        bottle = next(entity for entity in view.entities if entity.id == "bottle_1")
        assert view.coins == 9
        assert bottle.state["price"] == 3
        assert bottle.state["for_sale_by"] == "npc_oren"

        purchase = game.execute(
            CanonicalAction(
                "player_legacy",
                ActionType.BUY,
                item_id="bottle_1",
                target_id="npc_oren",
            ),
            external_id="migration-demo-buy",
        )
        assert purchase.success
        assert game.observe("player_legacy").coins == 6
        print("[current rules] Migrated DB executes BUY: player 9 -> 6, Oren 20 -> 23")
        print("\nSQLite Migration demo: PASS")


if __name__ == "__main__":
    main()
